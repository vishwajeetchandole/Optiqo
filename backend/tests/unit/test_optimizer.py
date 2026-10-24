"""
Optiqo — Unit Tests for Lot-by-Lot Allocation Optimizer (Phase 4, PRD §10.2, §10.3, §10.5)

Verifies:
- OptimizerAdapter conforms to OptimizerProtocol.
- Optimal LP solve on clean dataset.
- Hard Constraint C1: Batch stock availability (sum_l x(b, l) <= Q_b).
- Hard Constraint C2: Lane and shelf-life eligibility (r >= m_s, unblocked).
- Hard Constraint C3: Destination capacity limit (volume <= capRoom).
- Hard Constraint C4: Integer round-down post-processing (whole units only).
- Hard Constraint C5: Lane pruning (at most k lowest-freight warehouses per (dest, SKU)).
- Graceful handling of empty or unfeasible inventory states.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.data.loader import load_dataset
from backend.engines.forecasting.adapter import ForecastingAdapter
from backend.engines.optimizer.adapter import OptimizerAdapter
from backend.engines.optimizer.rounding import round_down_allocations
from backend.engines.protocols import (
    ForecastRequestPayload,
    OptimizerConfig,
    OptimizerEngineOutput,
    OptimizerProtocol,
)
from backend.services.inventory import partition_warehouse_stock


def test_round_down_allocations():
    raw = {
        ("B01", "D01"): 12.8,
        ("B02", "D02"): 5.1,
        ("B03", "D03"): 0.005,  # below threshold
    }
    rounded, loss = round_down_allocations(raw, threshold=0.01)

    assert rounded[("B01", "D01")] == 12
    assert rounded[("B02", "D02")] == 5
    assert ("B03", "D03") not in rounded
    # Total loss = 0.8 + 0.1 = 0.9 -> round to 1
    assert loss == 1


def test_optimizer_adapter_protocol():
    adapter = OptimizerAdapter()
    assert isinstance(adapter, OptimizerProtocol)


def test_optimizer_solves_on_clean_data(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    origin = "2024-01-15"

    # 1. Generate forecasts
    f_adapter = ForecastingAdapter(seed=42)
    f_output = f_adapter.generate_forecast(
        ForecastRequestPayload(
            sales_daily=ds.sales_daily,
            skus=ds.skus,
            calendar_events=ds.calendar_events,
            destinations=ds.destinations,
            origin_date=origin,
            horizon_days=7,
        )
    )

    # 2. Prepare usable inventory
    usable_wh, _ = partition_warehouse_stock(
        date.fromisoformat(origin), ds.inventory_batches, ds.lanes, ds.skus
    )

    opt_adapter = OptimizerAdapter()
    config = OptimizerConfig(
        shortage_penalty_factor=1.5,
        holding_cost_rate=0.02,
        lane_pruning_k=3,
        solver_timeout_seconds=60,
    )

    output = opt_adapter.optimize_allocation(
        usable_inventory=usable_wh,
        forecast_table=f_output.forecast_table,
        destinations=ds.destinations,
        skus=ds.skus,
        lanes=ds.lanes,
        config=config,
        origin_date=origin,
    )

    assert isinstance(output, OptimizerEngineOutput)
    assert output.status in ("OPTIMAL", "SOLVER_TIMEOUT")
    assert output.objective_value >= 0.0
    assert output.rounding_loss_units >= 0
    assert len(output.lines) > 0

    # ── Constraint C1 Verification: Batch Stock Availability ─────────────────
    batch_caps = dict(zip(usable_wh["batch_id"].astype(str), usable_wh["quantity"]))
    allocated_by_batch: dict[str, int] = {}
    for line in output.lines:
        allocated_by_batch[line.batch_id] = allocated_by_batch.get(line.batch_id, 0) + line.quantity

    for b_id, alloc_qty in allocated_by_batch.items():
        assert alloc_qty <= batch_caps.get(b_id, 0.0) + 0.01, \
            f"Batch {b_id} allocation ({alloc_qty}) exceeded stock ({batch_caps.get(b_id)})"

    # ── Constraint C2 Verification: Shelf-Life Eligibility ───────────────────
    for line in output.lines:
        assert line.remaining_life_at_arrival >= line.min_required_life, \
            f"Line {line.line_id} violated minimum shelf life (remaining={line.remaining_life_at_arrival}, min={line.min_required_life})"
        assert line.quantity > 0

    # ── Constraint C3 Verification: Destination Storage Capacity ─────────────
    sku_vols = dict(zip(ds.skus["sku_id"].astype(str), ds.skus["unit_volume"]))
    dest_caps = dict(zip(ds.destinations["dest_id"].astype(str), ds.destinations["storage_capacity"]))
    dest_allocated_vol: dict[str, float] = {}

    for line in output.lines:
        vol = sku_vols.get(line.sku_id, 1.0)
        dest_allocated_vol[line.dest_id] = dest_allocated_vol.get(line.dest_id, 0.0) + (line.quantity * vol)

    for d_id, alloc_vol in dest_allocated_vol.items():
        assert alloc_vol <= dest_caps.get(d_id, 99999.0) + 1.0, \
            f"Destination {d_id} allocated volume ({alloc_vol}) exceeded capacity ({dest_caps.get(d_id)})"

    # ── Constraint C4 Verification: Integer Allocations ──────────────────────
    for line in output.lines:
        assert isinstance(line.quantity, int)
        assert line.quantity >= 1

    # ── Constraint C5 Verification: Lane Pruning ─────────────────────────────
    whs_per_dest_sku: dict[tuple[str, str], set[str]] = {}
    for line in output.lines:
        key = (line.dest_id, line.sku_id)
        if key not in whs_per_dest_sku:
            whs_per_dest_sku[key] = set()
        whs_per_dest_sku[key].add(line.warehouse_id)

    for (d_id, s_id), wh_set in whs_per_dest_sku.items():
        assert len(wh_set) <= config.lane_pruning_k, \
            f"Dest-SKU ({d_id}, {s_id}) shipped from {len(wh_set)} warehouses, exceeding k={config.lane_pruning_k}"


def test_optimizer_handles_empty_inventory_gracefully(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    opt_adapter = OptimizerAdapter()
    config = OptimizerConfig()

    empty_inventory = pd.DataFrame(columns=ds.inventory_batches.columns)
    dummy_forecast = pd.DataFrame(columns=["dest_id", "sku_id", "low_horizon_demand", "mid_horizon_demand", "high_horizon_demand"])

    output = opt_adapter.optimize_allocation(
        usable_inventory=empty_inventory,
        forecast_table=dummy_forecast,
        destinations=ds.destinations,
        skus=ds.skus,
        lanes=ds.lanes,
        config=config,
    )

    assert output.status == "OPTIMAL"
    assert len(output.lines) == 0
    assert output.objective_value == 0.0
