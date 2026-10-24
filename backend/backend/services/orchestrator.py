"""
Optiqo — Single-Cycle Planning Orchestrator (PRD §5.1, Plan §3.1, §6)

Coordinates the complete Phase 5 planning workflow in strict sequential order:
1. Load dataset (demo data or custom path)
2. Validate dataset (fail fast on blocking errors)
3. Inventory preparation & shelf-life eligibility
4. Demand forecasting (LightGBM & multi-step baselines)
5. Pre-plan risk evaluation
6. Lot-by-lot linear program optimization
7. Independent constraint verification (C1–C5)
8. Grounded explanation & evidence generation
9. Assembly of final PlanResponse
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import time
from typing import Any, Optional
import uuid

import pandas as pd

from backend.core.config import settings
from backend.core.exceptions import (
    DataError,
    ForecastError,
    InfeasibleError,
    MissingDatasetError,
    OptiqoError,
    SolverTimeoutError,
    ValidationError,
)
from backend.core.logging import get_logger
from backend.data.loader import load_dataset
from backend.data.validator import validate_dataset
from backend.engines.forecasting.adapter import ForecastingAdapter
from backend.engines.optimizer.adapter import OptimizerAdapter
from backend.engines.protocols import (
    ConstraintVerifierProtocol,
    ForecastRequestPayload,
    ForecasterProtocol,
    OptimizerConfig,
    OptimizerProtocol,
)
from backend.engines.verification.checker import ConstraintVerifier
from backend.schemas.plan import (
    CheckerStatus,
    ConstraintViolationItem,
    PlanLineItem,
    PlanRequest,
    PlanResponse,
    PlanSummary,
)
from backend.services.explainer import generate_plan_explanations
from backend.services.inventory import (
    get_destination_lots,
    partition_warehouse_stock,
)
from backend.services.risk import compute_risk_overview

logger = get_logger(__name__)


def run_planning_cycle(
    request: PlanRequest,
    forecaster: Optional[ForecasterProtocol] = None,
    optimizer: Optional[OptimizerProtocol] = None,
    verifier: Optional[ConstraintVerifierProtocol] = None,
) -> PlanResponse:
    """
    Execute a single-cycle end-to-end planning run with strict independent verification.
    """
    cycle_start = time.perf_counter()
    logger.info("Starting single-cycle planning run for origin_date=%s", request.origin_date)

    # 1. Parse and validate origin_date
    try:
        parsed_origin = date.fromisoformat(str(request.origin_date)[:10])
    except ValueError:
        raise DataError(
            message=f"Invalid origin_date format: '{request.origin_date}'. Expected ISO-8601 YYYY-MM-DD."
        )

    # 2. Resolve dataset directory
    if request.dataset_path:
        data_dir = Path(request.dataset_path)
        if not data_dir.is_absolute():
            data_dir = settings.BASE_DIR / request.dataset_path
    else:
        data_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"

    if not data_dir.exists():
        raise MissingDatasetError(
            message=f"Dataset directory not found: {data_dir}. Generate demo data first or specify dataset_path."
        )

    # 3. Validate dataset with 13-fault validation engine (Fail fast on blocking errors)
    val_errors, val_warnings = validate_dataset(
        data_dir=data_dir,
        planning_date=parsed_origin,
    )
    if val_errors:
        error_details = [
            f"[{e.table}.{e.field or '*'}] {e.rule}: {e.message}"
            for e in val_errors
        ]
        logger.warning(
            "Planning aborted due to %d blocking validation errors: %s",
            len(val_errors),
            error_details[:3],
        )
        raise ValidationError(
            message=f"Dataset validation failed with {len(val_errors)} blocking errors.",
            details=error_details,
        )

    # 4. Load dataset tables
    loaded_ds, load_errs = load_dataset(data_dir)
    if loaded_ds is None or load_errs:
        raise MissingDatasetError(
            message=f"Dataset at {data_dir} is incomplete or missing required tables: {load_errs}"
        )
    dataset = loaded_ds.as_dict()

    # 5. Inventory Preparation
    initial_batches = dataset["inventory_batches"]
    destinations = dataset["destinations"]
    skus = dataset["skus"]
    lanes = dataset["lanes"]
    inbound_shipments = dataset.get("inbound_shipments")
    sales_daily = dataset["sales_daily"]
    calendar_events = dataset["calendar_events"]

    usable_inv, unusable_inv = partition_warehouse_stock(
        origin_date=parsed_origin,
        batches_df=initial_batches,
        lanes_df=lanes,
        skus_df=skus,
    )

    # 6. Demand Forecasting
    if forecaster is None:
        forecaster = ForecastingAdapter()

    fc_payload = ForecastRequestPayload(
        sales_daily=sales_daily,
        skus=skus,
        calendar_events=calendar_events,
        destinations=destinations,
        origin_date=request.origin_date,
        horizon_days=request.horizon_days,
    )

    fc_output = forecaster.generate_forecast(fc_payload)
    if fc_output.status == "ERROR":
        raise ForecastError("Demand forecasting engine failed to generate forecasts.")
    forecast_table = fc_output.forecast_table

    # 7. Pre-Plan Risk Evaluation (x = 0)
    pre_risk = compute_risk_overview(
        origin_date=parsed_origin,
        loaded_dataset=loaded_ds,
        horizon_days=request.horizon_days,
    )
    expected_unmet_before = round(
        sum(a.expected_unmet_units for a in pre_risk.alerts), 1
    )
    expected_expiry_before = round(
        sum(a.expected_expiry_units for a in pre_risk.alerts), 1
    )
    unmet_before_by_dest_sku = {
        (str(a.dest_id), str(a.sku_id)): float(a.expected_unmet_units)
        for a in pre_risk.alerts
    }
    expiry_before_by_dest_sku = {
        (str(a.dest_id), str(a.sku_id)): float(a.expected_expiry_units)
        for a in pre_risk.alerts
    }

    # 8. Allocation Optimization Solve
    if optimizer is None:
        optimizer = OptimizerAdapter()

    opt_config = OptimizerConfig(
        shortage_penalty_factor=request.cost_parameters.shortage_penalty_factor
        if request.cost_parameters
        else 1.5,
        holding_cost_rate=request.cost_parameters.holding_cost_rate
        if request.cost_parameters
        else 0.02,
        lane_pruning_k=request.lane_pruning_k,
        solver_timeout_seconds=request.solver_timeout_seconds,
    )

    opt_output = optimizer.optimize_allocation(
        usable_inventory=usable_inv,
        forecast_table=forecast_table,
        destinations=destinations,
        skus=skus,
        lanes=lanes,
        config=opt_config,
        origin_date=request.origin_date,
    )

    if opt_output.status == "ERROR":
        raise OptiqoError("Optimizer execution failed.")
    elif opt_output.status == "INFEASIBLE":
        raise InfeasibleError("Linear program allocation is infeasible.")
    elif opt_output.status == "SOLVER_TIMEOUT" and not opt_output.lines:
        raise SolverTimeoutError("Solver timed out before finding a feasible integer allocation.")

    # 9. Independent Constraint Verification (Hard Constraints C1–C5)
    if verifier is None:
        verifier = ConstraintVerifier()

    verification_result = verifier.verify_plan(
        plan_lines=opt_output.lines,
        initial_batches=initial_batches,
        destinations=destinations,
        skus=skus,
        lanes=lanes,
        origin_date=request.origin_date,
        inbound_shipments=inbound_shipments,
        destination_batches=initial_batches,
        lane_pruning_k=request.lane_pruning_k,
        warehouses=dataset.get("warehouses"),
    )

    checker_status = CheckerStatus(
        passed=verification_result.passed,
        violations_count=verification_result.total_violations,
        violations=[
            ConstraintViolationItem(
                constraint_id=v.constraint_id,
                entity_id=v.entity_id,
                violation_message=v.violation_message,
                observed_value=v.observed_value,
                limit_value=v.limit_value,
            )
            for v in verification_result.violations
        ],
    )

    # 10. Post-Plan Metrics & Supply-Bound Shortage (O5)
    unmet_df = opt_output.unmet_demand_by_dest_sku
    expiry_df = opt_output.expected_expiry_by_dest_sku
    scenario_weights = {"low": 0.3, "mid": 0.4, "high": 0.3}

    if not unmet_df.empty:
        if "scenario" in unmet_df.columns and "unmet_units" in unmet_df.columns:
            unmet_work = unmet_df.copy()
            unmet_work["weighted_unmet"] = unmet_work.apply(
                lambda r: float(r["unmet_units"]) * scenario_weights.get(str(r["scenario"]).lower(), 0.333),
                axis=1,
            )
            grouped_unmet = unmet_work.groupby(["dest_id", "sku_id"])["weighted_unmet"].sum().reset_index()
            expected_unmet_after = round(float(grouped_unmet["weighted_unmet"].sum()), 1)
            unmet_after_by_dest_sku = {
                (str(r["dest_id"]), str(r["sku_id"])): float(r["weighted_unmet"])
                for _, r in grouped_unmet.iterrows()
            }
        else:
            val_col = "unmet_units" if "unmet_units" in unmet_df.columns else unmet_df.columns[-1]
            expected_unmet_after = round(float(unmet_df[val_col].sum()), 1)
            unmet_after_by_dest_sku = {
                (str(r["dest_id"]), str(r["sku_id"])): float(r[val_col])
                for _, r in unmet_df.iterrows()
            }
    else:
        expected_unmet_after = 0.0
        unmet_after_by_dest_sku = {}

    if not expiry_df.empty:
        if "scenario" in expiry_df.columns and "expected_expiry_units" in expiry_df.columns:
            expiry_work = expiry_df.copy()
            expiry_work["weighted_expiry"] = expiry_work.apply(
                lambda r: float(r["expected_expiry_units"]) * scenario_weights.get(str(r["scenario"]).lower(), 0.333),
                axis=1,
            )
            grouped_expiry = expiry_work.groupby(["dest_id", "sku_id"])["weighted_expiry"].sum().reset_index()
            expected_expiry_after = round(float(grouped_expiry["weighted_expiry"].sum()), 1)
            expiry_after_by_dest_sku = {
                (str(r["dest_id"]), str(r["sku_id"])): float(r["weighted_expiry"])
                for _, r in grouped_expiry.iterrows()
            }
        else:
            val_col = "expected_expiry_units" if "expected_expiry_units" in expiry_df.columns else expiry_df.columns[-1]
            expected_expiry_after = round(float(expiry_df[val_col].sum()), 1)
            expiry_after_by_dest_sku = {
                (str(r["dest_id"]), str(r["sku_id"])): float(r[val_col])
                for _, r in expiry_df.iterrows()
            }
    else:
        expected_expiry_after = 0.0
        expiry_after_by_dest_sku = {}

    # Metric O5: Supply-bound unavoidable shortage
    # Sum over SKUs of max(0, total_expected_demand_s - total_usable_network_stock_s)
    # Network stock = usable warehouse stock + destination on-hand stock
    dest_lots = get_destination_lots(
        origin_date=parsed_origin,
        horizon_days=request.horizon_days,
        batches_df=initial_batches,
        inbound_df=inbound_shipments,
    )

    supply_bound_shortage = 0.0
    for s_id in skus["sku_id"].unique():
        s_id_str = str(s_id)
        sku_fc = forecast_table[forecast_table["sku_id"].astype(str) == s_id_str]
        exp_dem = float(sku_fc["horizon_mean"].sum()) if not sku_fc.empty else 0.0

        wh_stock = float(
            usable_inv[usable_inv["sku_id"].astype(str) == s_id_str]["quantity"].sum()
        ) if not usable_inv.empty else 0.0
        dest_stock = float(
            dest_lots[dest_lots["sku_id"].astype(str) == s_id_str]["quantity"].sum()
        ) if not dest_lots.empty else 0.0

        tot_stock = wh_stock + dest_stock
        if exp_dem > tot_stock:
            supply_bound_shortage += (exp_dem - tot_stock)

    supply_bound_shortage = round(supply_bound_shortage, 1)
    allocation_caused_shortage = round(
        max(0.0, expected_unmet_after - supply_bound_shortage), 1
    )

    total_shipped = int(sum(l.quantity for l in opt_output.lines))
    total_freight = round(sum(l.total_freight_cost for l in opt_output.lines), 2)

    summary = PlanSummary(
        total_shipped_units=total_shipped,
        total_freight_cost=total_freight,
        expected_unmet_demand_before=expected_unmet_before,
        expected_unmet_demand_after=expected_unmet_after,
        expected_expiry_loss_before=expected_expiry_before,
        expected_expiry_loss_after=expected_expiry_after,
        supply_bound_unavoidable_shortage=supply_bound_shortage,
        allocation_caused_shortage=allocation_caused_shortage,
    )

    # 11. Grounded Explanations (Grounded on verified evidence)
    plan_line_items = generate_plan_explanations(
        plan_lines=opt_output.lines,
        forecast_table=forecast_table,
        initial_batches=initial_batches,
        destinations=destinations,
        skus=skus,
        lanes=lanes,
        unmet_before_by_dest_sku=unmet_before_by_dest_sku,
        unmet_after_by_dest_sku=unmet_after_by_dest_sku,
        expiry_before_by_dest_sku=expiry_before_by_dest_sku,
        expiry_after_by_dest_sku=expiry_after_by_dest_sku,
    )

    # 12. Final Status & Response
    # If independent verification failed, mark plan status explicitly UNVERIFIED
    plan_status = "OK" if verification_result.passed else "UNVERIFIED"
    solver_status = opt_output.status
    if not verification_result.passed:
        logger.warning(
            "Plan independent verification failed with %d violations! Status set to UNVERIFIED.",
            verification_result.total_violations,
        )

    run_id = f"run_{request.origin_date.replace('-', '')}_{uuid.uuid4().hex[:8]}"

    response = PlanResponse(
        status=plan_status,
        run_id=run_id,
        origin_date=request.origin_date,
        solver_status=solver_status,
        solver_runtime_seconds=round(opt_output.solver_runtime_seconds, 2),
        checker_status=checker_status,
        summary=summary,
        plan_lines=plan_line_items,
    )

    # 13. Persist Run Manifest (Phase 7)
    try:
        from backend.storage.repository import compute_dataset_hash, save_run
        manifest_data = {
            "run_id": run_id,
            "run_type": "PLAN",
            "origin_date": request.origin_date,
            "dataset_hash": compute_dataset_hash(data_dir),
            "parameters": {
                "origin_date": request.origin_date,
                "horizon_days": request.horizon_days,
                "lane_pruning_k": request.lane_pruning_k,
                "solver_timeout_seconds": request.solver_timeout_seconds,
                "cost_parameters": request.cost_parameters.model_dump() if request.cost_parameters else None,
            },
            "status": plan_status,
            "solver_status": solver_status,
            "solver_runtime_seconds": round(opt_output.solver_runtime_seconds, 2),
            "checker_verdict": checker_status.model_dump(),
            "summary": summary.model_dump(),
            "plan_lines": [line.model_dump() for line in plan_line_items],
            "available_artifacts": ["plan", "risks", "kpis"],
        }
        save_run(manifest_data)
    except Exception as e:
        logger.warning("Failed to persist plan run manifest %s: %s", run_id, e)

    logger.info(
        "Planning cycle completed in %.2fs: status=%s, lines=%d, shipped=%d, violations=%d",
        time.perf_counter() - cycle_start,
        plan_status,
        len(plan_line_items),
        total_shipped,
        verification_result.total_violations,
    )
    return response
