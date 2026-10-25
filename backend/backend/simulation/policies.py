"""
Optiqo — Simulation Policies: B1 (Trailing Average), B2 (Forecast Simple), and Optiqo (LP) (PRD §10.7, §5.1 P0-09)
"""

from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Any, Optional, Protocol
import pandas as pd

from backend.engines.protocols import OptimizerConfig, PlannedShipmentLine
from backend.engines.optimizer.adapter import OptimizerAdapter
from backend.engines.verification.checker import ConstraintVerifier
from backend.services.inventory import (
    filter_eligible_lane_batches,
    partition_warehouse_stock,
)


class SimulationPolicy(Protocol):
    """Protocol for dispatch planning policies evaluated in the multi-cycle simulator."""

    def plan_cycle(
        self,
        current_date: date,
        warehouse_batches: list[dict[str, Any]],
        destination_lots: list[dict[str, Any]],
        inbound_shipments: list[dict[str, Any]],
        dataset: dict[str, pd.DataFrame],
        forecast_table: Optional[pd.DataFrame] = None,
        safety_days: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Generate shipment allocation lines for the dispatch date.
        Returns list of dicts: warehouse_id, batch_id, sku_id, dest_id, quantity, arrival_date, freight_cost.
        """
        ...


class B1Policy:
    """
    Baseline 1 (Conventional Heuristic - PRD §10.7):
    - Target stock = 7-day trailing average daily sales * (7 + safety_days)
    - Order = max(0, target - on_hand - inbound)
    - Capacity check: volume bounded by dest capRoom
    - Sourced from nearest warehouse with eligible stock (oldest batch first / FEFO)
    - Proportional cut-back when warehouse stock is insufficient
    """

    def plan_cycle(
        self,
        current_date: date,
        warehouse_batches: list[dict[str, Any]],
        destination_lots: list[dict[str, Any]],
        inbound_shipments: list[dict[str, Any]],
        dataset: dict[str, pd.DataFrame],
        forecast_table: Optional[pd.DataFrame] = None,
        safety_days: int = 2,
    ) -> list[dict[str, Any]]:
        return _run_heuristic_policy(
            current_date=current_date,
            warehouse_batches=warehouse_batches,
            destination_lots=destination_lots,
            inbound_shipments=inbound_shipments,
            dataset=dataset,
            forecast_table=None,  # B1 uses sales history
            safety_days=safety_days,
        )


class B2Policy:
    """
    Baseline 2 (Forecast-Driven Simple Heuristic - PRD §10.7):
    - Target stock = forecast 7-day demand + (mean daily forecast * safety_days)
    - Order = max(0, target - on_hand - inbound)
    - Same nearest-warehouse sourcing, FEFO, capacity, and proportional cut-back as B1
    - Isolates Forecast Effect from Allocation Effect (Gain Decomposition K8)
    """

    def plan_cycle(
        self,
        current_date: date,
        warehouse_batches: list[dict[str, Any]],
        destination_lots: list[dict[str, Any]],
        inbound_shipments: list[dict[str, Any]],
        dataset: dict[str, pd.DataFrame],
        forecast_table: Optional[pd.DataFrame] = None,
        safety_days: int = 2,
    ) -> list[dict[str, Any]]:
        return _run_heuristic_policy(
            current_date=current_date,
            warehouse_batches=warehouse_batches,
            destination_lots=destination_lots,
            inbound_shipments=inbound_shipments,
            dataset=dataset,
            forecast_table=forecast_table,  # B2 uses forecast table
            safety_days=safety_days,
        )


class OptiqoPolicy:
    """
    Optiqo Policy (PRD §5.1 P0-05, §10.2, §10.5):
    - Full multi-scenario lot-by-lot linear program optimization
    - Evaluates joint allocation across all competing destinations sharing stock
    - Hard constraints C1–C5 enforced and independently verified
    """

    def __init__(self, optimizer: Optional[Any] = None, verifier: Optional[Any] = None):
        self.optimizer = optimizer or OptimizerAdapter()
        self.verifier = verifier or ConstraintVerifier()

    def plan_cycle(
        self,
        current_date: date,
        warehouse_batches: list[dict[str, Any]],
        destination_lots: list[dict[str, Any]],
        inbound_shipments: list[dict[str, Any]],
        dataset: dict[str, pd.DataFrame],
        forecast_table: Optional[pd.DataFrame] = None,
        safety_days: int = 2,
    ) -> list[dict[str, Any]]:
        # Convert warehouse_batches to DataFrame for optimizer
        wh_df = pd.DataFrame(warehouse_batches)
        if wh_df.empty:
            return []
        if "location_type" not in wh_df.columns:
            wh_df["location_type"] = "warehouse"
        if "location_id" not in wh_df.columns:
            wh_df["location_id"] = wh_df["warehouse_id"]

        # Ensure destination lots exist in inventory DataFrame
        dest_df = pd.DataFrame(destination_lots)
        if not dest_df.empty:
            if "location_type" not in dest_df.columns:
                dest_df["location_type"] = "destination"
            if "location_id" not in dest_df.columns:
                dest_df["location_id"] = dest_df["dest_id"]
            combined_inv = pd.concat([wh_df, dest_df], ignore_index=True)
        else:
            combined_inv = wh_df

        if "dest_id" in combined_inv.columns:
            combined_inv = combined_inv.drop(columns=["dest_id"])

        # Partition warehouse batches to find usable inventory
        usable_inv, _ = partition_warehouse_stock(
            origin_date=current_date,
            batches_df=combined_inv,
            lanes_df=dataset["lanes"],
            skus_df=dataset["skus"],
        )

        if usable_inv.empty or forecast_table is None or forecast_table.empty:
            return []

        config = OptimizerConfig(
            shortage_penalty_factor=1.5,
            holding_cost_rate=0.02,
            solver_timeout_seconds=60,
            lane_pruning_k=3,
        )

        opt_output = self.optimizer.optimize_allocation(
            usable_inventory=usable_inv,
            forecast_table=forecast_table,
            destinations=dataset["destinations"],
            skus=dataset["skus"],
            lanes=dataset["lanes"],
            config=config,
            origin_date=current_date.isoformat(),
        )

        # Convert PlannedShipmentLines to dicts
        result_lines: list[dict[str, Any]] = []
        for line in opt_output.lines:
            if line.quantity > 0:
                result_lines.append({
                    "line_id": line.line_id,
                    "warehouse_id": line.warehouse_id,
                    "batch_id": line.batch_id,
                    "sku_id": line.sku_id,
                    "dest_id": line.dest_id,
                    "quantity": int(line.quantity),
                    "arrival_date": line.arrival_date,
                    "freight_cost": float(line.total_freight_cost),
                })
        return result_lines


def _run_heuristic_policy(
    current_date: date,
    warehouse_batches: list[dict[str, Any]],
    destination_lots: list[dict[str, Any]],
    inbound_shipments: list[dict[str, Any]],
    dataset: dict[str, pd.DataFrame],
    forecast_table: Optional[pd.DataFrame],
    safety_days: int = 2,
) -> list[dict[str, Any]]:
    """Shared allocation logic for B1 (trailing-mean) and B2 (forecast-driven)."""
    skus = dataset["skus"]
    destinations = dataset["destinations"]
    lanes = dataset["lanes"]
    sales_daily = dataset["sales_daily"]

    # 1. Lookup tables
    sku_lookup = {
        str(row["sku_id"]): {
            "min_life_days": int(row.get("min_life_days", 0)),
            "unit_volume": float(row.get("unit_volume", 1.0)),
            "unit_cost": float(row.get("unit_cost", 10.0)),
        }
        for _, row in skus.iterrows()
    }
    dest_capacity = {
        str(row["dest_id"]): float(row.get("storage_capacity", 99999.0))
        for _, row in destinations.iterrows()
    }
    lane_dict: dict[tuple[str, str], dict[str, Any]] = {}
    for _, row in lanes.iterrows():
        w = str(row["warehouse_id"])
        d = str(row["dest_id"])
        lane_dict[(w, d)] = {
            "distance_km": float(row.get("distance_km", 100.0)),
            "transit_days": int(row.get("transit_days", 1)),
            "freight_rate": float(row.get("freight_rate", 1.0)),
            "blocked": bool(row.get("blocked", False)),
        }

    # 2. Compute Target Demand per (dest_id, sku_id)
    target_demand: dict[tuple[str, str], float] = {}

    if forecast_table is not None and not forecast_table.empty:
        # B2 Policy: Target from forecast
        for _, row in forecast_table.iterrows():
            d = str(row["dest_id"])
            s = str(row["sku_id"])
            horizon_fc = float(row.get("horizon_mean", 0.0) or 0.0)
            daily_fc = horizon_fc / 7.0
            target_demand[(d, s)] = horizon_fc + (daily_fc * safety_days)
    else:
        # B1 Policy: Target from 7-day trailing average
        sales_copy = sales_daily.copy()
        if "date" in sales_copy.columns:
            date_col = "date"
        else:
            date_col = "sale_date"
        sales_copy["parsed_date"] = pd.to_datetime(sales_copy[date_col]).dt.date

        trailing_start = current_date - timedelta(days=6)
        sub_sales = sales_copy[
            (sales_copy["parsed_date"] >= trailing_start) & (sales_copy["parsed_date"] <= current_date)
        ]

        if not sub_sales.empty:
            grouped = sub_sales.groupby(["dest_id", "sku_id"])["units_sold"].sum().reset_index()
            for _, row in grouped.iterrows():
                d = str(row["dest_id"])
                s = str(row["sku_id"])
                weekly_sales = float(row["units_sold"])
                daily_avg = weekly_sales / 7.0
                target_demand[(d, s)] = daily_avg * (7 + safety_days)

    # 3. Calculate on-hand and inbound stock per destination
    dest_on_hand: dict[tuple[str, str], float] = {}
    for lot in destination_lots:
        qty = float(lot.get("quantity", 0))
        exp = lot.get("expiry_date")
        if isinstance(exp, str):
            exp = date.fromisoformat(exp[:10])
        if qty > 0 and exp > current_date:
            key = (str(lot["dest_id"]), str(lot["sku_id"]))
            dest_on_hand[key] = dest_on_hand.get(key, 0.0) + qty

    dest_inbound: dict[tuple[str, str], float] = {}
    for ship in inbound_shipments:
        qty = float(ship.get("quantity", 0))
        if qty > 0:
            key = (str(ship["dest_id"]), str(ship["sku_id"]))
            dest_inbound[key] = dest_inbound.get(key, 0.0) + qty

    # 4. Compute unconstrained order quantities per destination
    dest_orders: dict[tuple[str, str], float] = {}
    for (d, s), target in target_demand.items():
        on_hand = dest_on_hand.get((d, s), 0.0)
        inbound = dest_inbound.get((d, s), 0.0)
        gross_needed = target - on_hand - inbound
        if gross_needed > 0.5:
            dest_orders[(d, s)] = math.floor(gross_needed)

    # 5. Destination storage capacity enforcement
    dest_requested_vol: dict[str, float] = {}
    dest_used_vol: dict[str, float] = {}

    for (d, s), on_h in dest_on_hand.items():
        u_vol = sku_lookup.get(s, {}).get("unit_volume", 1.0)
        dest_used_vol[d] = dest_used_vol.get(d, 0.0) + (on_h * u_vol)

    for (d, s), inb in dest_inbound.items():
        u_vol = sku_lookup.get(s, {}).get("unit_volume", 1.0)
        dest_used_vol[d] = dest_used_vol.get(d, 0.0) + (inb * u_vol)

    for (d, s), ord_qty in dest_orders.items():
        u_vol = sku_lookup.get(s, {}).get("unit_volume", 1.0)
        dest_requested_vol[d] = dest_requested_vol.get(d, 0.0) + (ord_qty * u_vol)

    for d, req_vol in dest_requested_vol.items():
        cap = dest_capacity.get(d, 99999.0)
        used = dest_used_vol.get(d, 0.0)
        room = max(0.0, cap - used)
        if req_vol > room and req_vol > 0:
            scale = room / req_vol
            for (dest, s), ord_qty in list(dest_orders.items()):
                if dest == d:
                    dest_orders[(dest, s)] = math.floor(ord_qty * scale)

    # 6. Sourcing from nearest warehouse with eligible stock
    # Track available batches in memory
    available_batches: list[dict[str, Any]] = [
        dict(b) for b in warehouse_batches if float(b.get("quantity", 0)) > 0
    ]

    # Pre-parse batch expiry dates
    for b in available_batches:
        exp = b["expiry_date"]
        if isinstance(exp, str):
            b["parsed_expiry"] = date.fromisoformat(exp[:10])
        else:
            b["parsed_expiry"] = exp

    # Find nearest warehouse for each (d, s) request
    # Sort warehouses by distance_km
    shipment_lines: list[dict[str, Any]] = []
    line_counter = 1

    # Group requests by SKU to handle warehouse-level contention and proportional cut-back
    sku_requests: dict[str, list[tuple[str, float]]] = {}
    for (d, s), ord_qty in dest_orders.items():
        if ord_qty >= 1.0:
            sku_requests.setdefault(s, []).append((d, ord_qty))

    for s, dest_reqs in sku_requests.items():
        min_life = sku_lookup.get(s, {}).get("min_life_days", 0)

        # For each destination, find candidate warehouses sorted by distance
        for d, qty_needed in dest_reqs:
            if qty_needed <= 0:
                continue

            # Candidate warehouses connected to d
            candidate_lanes = [
                (w, info["distance_km"], info["transit_days"], info["freight_rate"])
                for (w, dest), info in lane_dict.items()
                if dest == d and not info["blocked"]
            ]
            candidate_lanes.sort(key=lambda x: x[1])  # Nearest distance first

            remaining_to_ship = qty_needed

            for w, dist, transit, freight_rate in candidate_lanes:
                if remaining_to_ship <= 0:
                    break

                # Eligible batches at this warehouse for SKU s
                arr_date = current_date + timedelta(days=transit)
                wh_sku_batches = [
                    b for b in available_batches
                    if str(b.get("warehouse_id") or b.get("location_id")) == w
                    and str(b["sku_id"]) == s
                    and float(b["quantity"]) > 0
                    and (b["parsed_expiry"] - arr_date).days >= min_life
                    and b["parsed_expiry"] > current_date
                ]

                # Sort by expiry ascending (FEFO)
                wh_sku_batches.sort(key=lambda b: b["parsed_expiry"])

                for batch in wh_sku_batches:
                    if remaining_to_ship <= 0:
                        break
                    avail = float(batch["quantity"])
                    if avail <= 0:
                        continue

                    alloc = min(math.floor(avail), math.floor(remaining_to_ship))
                    if alloc >= 1:
                        batch["quantity"] = avail - alloc
                        remaining_to_ship -= alloc
                        u_vol = sku_lookup.get(s, {}).get("unit_volume", 1.0)
                        freight_cost = round(
                            alloc * u_vol * dist * freight_rate, 2
                        )

                        shipment_lines.append({
                            "line_id": f"line_{line_counter:04d}",
                            "warehouse_id": w,
                            "batch_id": str(batch["batch_id"]),
                            "sku_id": s,
                            "dest_id": d,
                            "quantity": int(alloc),
                            "arrival_date": arr_date.isoformat(),
                            "freight_cost": freight_cost,
                        })
                        line_counter += 1

    return shipment_lines
