"""
Optiqo — Recommendation Explanations & Evidence Service (PRD §5.1 P0-08, §10.9, §7.4 O3)

Generates traceable evidence dictionaries and strictly controlled sentence templates
for every planned shipment line item. Ensures 100% numerical consistency between
evidence data and human-readable explanation strings.
"""

from __future__ import annotations

from typing import Any, Optional
import pandas as pd

from backend.engines.protocols import PlannedShipmentLine
from backend.schemas.plan import PlanLineEvidence, PlanLineExplanation, PlanLineItem


def generate_plan_explanations(
    plan_lines: list[PlannedShipmentLine],
    forecast_table: pd.DataFrame,
    initial_batches: pd.DataFrame,
    destinations: pd.DataFrame,
    skus: pd.DataFrame,
    lanes: pd.DataFrame,
    unmet_before_by_dest_sku: Optional[dict[tuple[str, str], float]] = None,
    unmet_after_by_dest_sku: Optional[dict[tuple[str, str], float]] = None,
    expiry_before_by_dest_sku: Optional[dict[tuple[str, str], float]] = None,
    expiry_after_by_dest_sku: Optional[dict[tuple[str, str], float]] = None,
) -> list[PlanLineItem]:
    """
    Generate grounded explanations and evidence dictionaries for each planned shipment line.
    
    Returns a list of PlanLineItem objects containing traceable evidence and
    unambiguous sentence templates with zero numerical discrepancy.
    """
    if not plan_lines:
        return []

    # 1. Pre-process forecast lookup: (dest_id, sku_id) -> {mean, low, high}
    forecast_lookup: dict[tuple[str, str], dict[str, float]] = {}
    if not forecast_table.empty:
        for _, row in forecast_table.iterrows():
            key = (str(row["dest_id"]), str(row["sku_id"]))
            forecast_lookup[key] = {
                "mean": float(row.get("horizon_mean", 0.0) or 0.0),
                "low": float(row.get("low_horizon_demand", 0.0) or 0.0),
                "high": float(row.get("high_horizon_demand", 0.0) or 0.0),
            }

    # 2. Pre-process destination inventory: (dest_id, sku_id) -> stock
    dest_stock_lookup: dict[tuple[str, str], float] = {}
    if "location_type" in initial_batches.columns:
        dest_batches = initial_batches[initial_batches["location_type"] == "destination"]
    else:
        dest_batches = pd.DataFrame()

    if not dest_batches.empty:
        for _, row in dest_batches.iterrows():
            key = (str(row["location_id"]), str(row["sku_id"]))
            dest_stock_lookup[key] = dest_stock_lookup.get(key, 0.0) + float(row.get("quantity", 0.0))

    # 3. Batch total initial quantities
    batch_initial_stock: dict[str, float] = {}
    wh_batches = initial_batches
    if "location_type" in initial_batches.columns:
        wh_batches = initial_batches[initial_batches["location_type"] == "warehouse"]
    for _, row in wh_batches.iterrows():
        b_id = str(row["batch_id"])
        batch_initial_stock[b_id] = float(row.get("quantity", 0.0))

    # Compute total allocated per batch across all lines to check if fully allocated
    batch_total_allocated: dict[str, float] = {}
    for line in plan_lines:
        b_id = str(line.batch_id)
        batch_total_allocated[b_id] = batch_total_allocated.get(b_id, 0.0) + float(line.quantity)

    # 4. Generate explanation for each line
    result_items: list[PlanLineItem] = []

    for line in plan_lines:
        d_id = str(line.dest_id)
        s_id = str(line.sku_id)
        w_id = str(line.warehouse_id)
        b_id = str(line.batch_id)
        qty = int(line.quantity)

        # Forecast
        fc = forecast_lookup.get((d_id, s_id), {"mean": 0.0, "low": 0.0, "high": 0.0})
        f_mean = round(fc["mean"], 1)
        f_low = round(fc["low"], 1)
        f_high = round(fc["high"], 1)

        # Inventory
        c_stock = round(dest_stock_lookup.get((d_id, s_id), 0.0), 1)
        inbound_stock = 0.0

        # Shelf life
        rem_life = int(line.remaining_life_at_arrival)
        min_life = int(line.min_required_life)

        # Freight costs
        freight_sel = round(float(line.total_freight_cost), 2)
        next_wh = line.next_best_warehouse_id
        freight_next: Optional[float] = None
        if line.next_best_freight_cost is not None and next_wh is not None:
            freight_next = round(float(line.next_best_freight_cost) * qty, 2)

        # Batch saturation & capacity
        init_qty = batch_initial_stock.get(b_id, 0.0)
        tot_alloc = batch_total_allocated.get(b_id, 0.0)
        is_fully_alloc = (tot_alloc >= init_qty > 0) or line.batch_fully_allocated
        is_cap_binding = line.destination_capacity_binding

        # Deltas
        dest_sku_key = (d_id, s_id)
        u_before = (unmet_before_by_dest_sku or {}).get(dest_sku_key, 0.0)
        u_after = (unmet_after_by_dest_sku or {}).get(dest_sku_key, 0.0)
        unmet_delta = round(u_after - u_before, 1)

        w_before = (expiry_before_by_dest_sku or {}).get(dest_sku_key, 0.0)
        w_after = (expiry_after_by_dest_sku or {}).get(dest_sku_key, 0.0)
        waste_delta = round(w_after - w_before, 1)

        # Construct Evidence
        evidence = PlanLineEvidence(
            forecast_mean=f_mean,
            forecast_range=[f_low, f_high],
            current_stock=c_stock,
            inbound_stock=inbound_stock,
            shipped_quantity=qty,
            remaining_shelf_life_arrival=rem_life,
            min_life_requirement=min_life,
            freight_cost_selected=freight_sel,
            freight_cost_next_best=freight_next,
            next_best_warehouse=next_wh,
            is_batch_fully_allocated=is_fully_alloc,
            is_destination_capacity_binding=is_cap_binding,
            expected_unmet_delta=unmet_delta,
            expected_waste_delta=waste_delta,
        )

        # Construct Sentence Template
        # Format: "Shipped {qty} units of {sku} from {wh} (batch {batch}, {rem} days shelf life remaining vs {min} min required) to {dest} to cover {f_mean:.0f} forecast units with current stock of {c_stock:.0f}"
        # + optional savings clause
        c_stock_str = f"{c_stock:.0f}" if c_stock.is_integer() else f"{c_stock:.1f}"
        f_mean_str = f"{f_mean:.0f}" if f_mean.is_integer() else f"{f_mean:.1f}"
        sentence_base = (
            f"Shipped {qty} units of {s_id} from {w_id} (batch {b_id}, "
            f"{rem_life} days shelf life remaining vs {min_life} min required) "
            f"to {d_id} to cover {f_mean_str} forecast units with current stock of {c_stock_str}"
        )

        if next_wh is not None and freight_next is not None and freight_next > freight_sel:
            saving = round(freight_next - freight_sel, 2)
            sentence = f"{sentence_base}, saving {saving:.2f} in freight vs {next_wh}."
        else:
            sentence = f"{sentence_base}."

        explanation = PlanLineExplanation(
            evidence=evidence,
            sentence=sentence,
        )

        item = PlanLineItem(
            line_id=line.line_id,
            warehouse_id=w_id,
            batch_id=b_id,
            sku_id=s_id,
            dest_id=d_id,
            quantity=qty,
            arrival_date=line.arrival_date,
            remaining_life_at_arrival_days=rem_life,
            min_required_life_days=min_life,
            freight_cost=freight_sel,
            explanation=explanation,
        )
        result_items.append(item)

    return result_items
