"""
Optiqo — Optimizer Post-Processing & Conservative Rounding (PRD §10.5 C4)

Implements:
- Conservative integer round-down post-processing of continuous LP shipment variables.
  Guarantees:
  - x_int(b, l) in NonNegativeIntegers.
  - Round-down cannot violate batch stock (C1) or destination storage capacity (C3).
  - Rounding loss units = sum(x - floor(x)) is tracked and reported.
- Construction of PlannedShipmentLine records with slack data and next-best freight comparisons.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd

from backend.engines.protocols import PlannedShipmentLine


def round_down_allocations(
    raw_allocations: dict[tuple[str, str], float],
    threshold: float = 0.01,
) -> tuple[dict[tuple[str, str], int], int]:
    """
    Round continuous LP shipment variables down to integer whole units (C4).
    Returns:
      (rounded_dict, total_rounding_loss_units)
    """
    rounded: dict[tuple[str, str], int] = {}
    total_loss = 0.0

    for key, val in raw_allocations.items():
        if val is None or val < threshold:
            continue
        int_val = math.floor(val)
        loss = val - int_val
        total_loss += loss
        if int_val > 0:
            rounded[key] = int_val

    return rounded, int(round(total_loss))


def construct_shipment_lines(
    rounded_allocations: dict[tuple[str, str], int],
    eligible_pairs_df: pd.DataFrame,
    batch_quantities: dict[str, float],
    dest_capacity_rooms: dict[str, float],
    lane_freights: dict[tuple[str, str], float],
) -> list[PlannedShipmentLine]:
    """
    Assemble PlannedShipmentLine items with economics, shelf life, and slack flags.
    """
    if not rounded_allocations or eligible_pairs_df.empty:
        return []

    # Map eligible pairs for quick lookup
    pair_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    wh_eligible_by_sku_dest: dict[tuple[str, str], list[tuple[str, float]]] = {}

    for _, row in eligible_pairs_df.iterrows():
        b_id = str(row["batch_id"])
        d_id = str(row["dest_id"])
        w_id = str(row["warehouse_id"])
        s_id = str(row["sku_id"])

        key = (b_id, d_id)
        pair_lookup[key] = row.to_dict()

        # Track freight costs per (dest, sku) across warehouses
        fr = float(row.get("freight_rate", 1.0) or 1.0)
        sd_key = (d_id, s_id)
        if sd_key not in wh_eligible_by_sku_dest:
            wh_eligible_by_sku_dest[sd_key] = []
        wh_eligible_by_sku_dest[sd_key].append((w_id, fr))

    # Compute batch total shipped units for batch_fully_allocated flag
    batch_shipped_total: dict[str, int] = {}
    dest_shipped_volume: dict[str, float] = {}

    for (b_id, d_id), qty in rounded_allocations.items():
        batch_shipped_total[b_id] = batch_shipped_total.get(b_id, 0) + qty
        info = pair_lookup.get((b_id, d_id), {})
        vol = float(info.get("unit_volume", 1.0) or 1.0)
        dest_shipped_volume[d_id] = dest_shipped_volume.get(d_id, 0.0) + (qty * vol)

    lines: list[PlannedShipmentLine] = []
    line_idx = 1

    for (b_id, d_id), qty in sorted(rounded_allocations.items()):
        info = pair_lookup.get((b_id, d_id), {})
        if not info:
            continue

        w_id = str(info.get("warehouse_id", ""))
        s_id = str(info.get("sku_id", ""))
        arr_date = str(info.get("arrival_date", ""))
        rem_life = int(info.get("remaining_life_at_arrival", 0))
        min_life = int(info.get("min_life_days", 0))
        fr_rate = float(info.get("freight_rate", 1.0) or 1.0)
        vol = float(info.get("unit_volume", 1.0) or 1.0)

        unit_freight = round(fr_rate * vol, 2)
        total_freight = round(unit_freight * qty, 2)

        # Batch fully allocated check: total shipped >= batch stock
        b_total = float(batch_quantities.get(b_id, 0.0))
        is_batch_full = batch_shipped_total.get(b_id, 0) >= (b_total - 0.5)

        # Destination capacity binding check: total volume >= capRoom
        cap_room = float(dest_capacity_rooms.get(d_id, 99999.0))
        is_cap_binding = dest_shipped_volume.get(d_id, 0.0) >= (cap_room - 1.0)

        # Next best warehouse and freight
        other_whs = [
            (ow, ofr)
            for ow, ofr in wh_eligible_by_sku_dest.get((d_id, s_id), [])
            if ow != w_id
        ]
        if other_whs:
            other_whs.sort(key=lambda x: x[1])
            next_wh, next_fr_rate = other_whs[0]
            next_fr_cost = round(next_fr_rate * vol, 2)
        else:
            next_wh = None
            next_fr_cost = None

        lines.append(
            PlannedShipmentLine(
                line_id=f"line_{line_idx:04d}",
                warehouse_id=w_id,
                batch_id=b_id,
                sku_id=s_id,
                dest_id=d_id,
                quantity=qty,
                arrival_date=arr_date,
                remaining_life_at_arrival=rem_life,
                min_required_life=min_life,
                unit_freight_cost=unit_freight,
                total_freight_cost=total_freight,
                batch_fully_allocated=is_batch_full,
                destination_capacity_binding=is_cap_binding,
                next_best_warehouse_id=next_wh,
                next_best_freight_cost=next_fr_cost,
            )
        )
        line_idx += 1

    return lines
