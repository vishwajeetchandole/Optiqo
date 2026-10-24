"""
Optiqo — Multi-Cycle Simulation & Backtest API Route (PRD §5.1 P0-09, §10.8, Plan §4.7)
  POST /api/backtest → Run multi-cycle rolling backtest comparing B1, B2, and Optiqo.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from fastapi import APIRouter

from backend.core.config import settings
from backend.core.exceptions import (
    DataError,
    MissingDatasetError,
    ValidationError,
)
from backend.core.logging import get_logger
from backend.data.loader import load_dataset
from backend.data.validator import validate_dataset
from backend.schemas.backtest import BacktestRequest, BacktestResponse
from backend.simulation.simulator import SimulationEngine

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/backtest",
    response_model=BacktestResponse,
    summary="Execute multi-cycle simulation and policy backtesting",
    description=(
        "Runs day-by-day rolling evaluation over the 56-day evaluation window across "
        "Baseline 1 (trailing-average heuristic), Baseline 2 (forecast-driven heuristic), "
        "and Optiqo (joint LP optimization). Evaluates business outcome KPIs K1–K8, "
        "gain decomposition, forecast accuracy F1–F5, and optimization quality O1–O5."
    ),
    tags=["Backtesting"],
)
def run_backtest_simulation(body: BacktestRequest) -> BacktestResponse:
    """Execute multi-cycle simulation and return backtest KPI comparison."""
    logger.info("Received POST /api/backtest: seed=%s, window=%d", body.seed, body.window_days)

    # 1. Resolve dataset directory
    if body.dataset_path:
        data_dir = Path(body.dataset_path)
        if not data_dir.is_absolute():
            data_dir = settings.BASE_DIR / body.dataset_path
    else:
        seed_val = body.seed or settings.DEFAULT_SEED
        data_dir = settings.demo_data_dir / f"seed_{seed_val}"

    if not data_dir.exists():
        raise MissingDatasetError(
            message=f"Dataset directory not found: {data_dir}. Generate demo data first or specify dataset_path."
        )

    # 2. Parse evaluation start date if provided
    parsed_start: date | None = None
    if body.evaluation_start_date:
        try:
            parsed_start = date.fromisoformat(str(body.evaluation_start_date)[:10])
        except ValueError:
            raise DataError(
                message=f"Invalid evaluation_start_date format: '{body.evaluation_start_date}'. Expected ISO-8601 YYYY-MM-DD."
            )

    # 3. Validate dataset with 13-fault validation engine
    val_errors, val_warnings = validate_dataset(
        data_dir=data_dir,
        planning_date=parsed_start or date(2024, 1, 15),
    )
    if val_errors:
        error_details = [
            f"[{e.table}.{e.field or '*'}] {e.rule}: {e.message}"
            for e in val_errors
        ]
        logger.warning(
            "Backtest aborted due to %d blocking validation errors: %s",
            len(val_errors),
            error_details[:3],
        )
        raise ValidationError(
            message=f"Dataset validation failed with {len(val_errors)} blocking errors.",
            details=error_details,
        )

    # 4. Load dataset tables
    loaded_ds, load_errs = load_dataset(data_dir)
    if loaded_ds is None:
        raise MissingDatasetError(
            message=f"Failed to load dataset from {data_dir}: {', '.join(load_errs)}"
        )

    dataset_dict = loaded_ds.as_dict()

    # 5. Run simulation engine
    engine = SimulationEngine()
    result = engine.run_backtest(
        dataset=dataset_dict,
        start_date=parsed_start,
        window_days=body.window_days,
        policies=body.policies,
        baseline_safety_days=body.baseline_safety_days,
        seed=body.seed or 42,
    )

    # 6. Persist Run Manifest (Phase 7)
    try:
        from backend.storage.repository import compute_dataset_hash, save_run
        manifest_data = {
            "run_id": result.run_id,
            "run_type": "BACKTEST",
            "origin_date": result.start_date,
            "seed": result.seed,
            "dataset_hash": compute_dataset_hash(data_dir),
            "parameters": {
                "evaluation_start_date": result.start_date,
                "window_days": result.window_days,
                "dispatch_cycles": result.dispatch_cycles,
                "policies": body.policies,
                "baseline_safety_days": body.baseline_safety_days,
            },
            "status": "COMPLETED",
            "summary": {
                "window_days": result.window_days,
                "dispatch_cycles": result.dispatch_cycles,
            },
            "kpi_comparison": result.kpi_comparison.model_dump() if hasattr(result.kpi_comparison, "model_dump") else result.kpi_comparison,
            "forecast_kpis": result.forecast_kpis.model_dump() if hasattr(result.forecast_kpis, "model_dump") else result.forecast_kpis,
            "optimization_kpis": result.optimization_kpis.model_dump() if hasattr(result.optimization_kpis, "model_dump") else result.optimization_kpis,
            "available_artifacts": ["kpis", "risks"],
        }
        save_run(manifest_data)
    except Exception as e:
        logger.warning("Failed to persist backtest run manifest %s: %s", result.run_id, e)

    return BacktestResponse(
        status="COMPLETED",
        run_id=result.run_id,
        window_days=result.window_days,
        dispatch_cycles=result.dispatch_cycles,
        seed=result.seed,
        kpi_comparison=result.kpi_comparison,
        forecast_kpis=result.forecast_kpis,
        optimization_kpis=result.optimization_kpis,
    )
