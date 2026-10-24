"""
Optiqo — Independent Constraint Verification Engine (PRD §5.1 P0-06, §7.4 O1, Plan §5.3)

Evaluates final integer-rounded shipment allocations against operational hard constraints C1–C5,
using raw input data completely independently of solver status flags or LP claims.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd

from backend.engines.protocols import (
    ConstraintVerifierProtocol,
    ConstraintViolation,
    PlannedShipmentLine,
    VerificationResult,
)
from backend.services.inventory import filter_eligible_lane_batches, get_destination_lots


class ConstraintVerifier(ConstraintVerifierProtocol):
    """
    Independent hard-constraint checker for Optiqo shipment plans.
    
    Verifies:
      - C1: Batch stock availability (allocations from each batch <= available stock)
      - C2: Shelf-life and lane eligibility (r(b,l) >= min_life, unblocked lane, unexpired)
      - C3: Destination capacity (allocated unit volume <= available capacity room)
      - C4: Non-negative integer quantities (whole units, quantity > 0)
      - C5: Lane pruning (at most k lowest-freight warehouses per (dest, SKU))
    """

    def verify_plan(
        self,
        plan_lines: list[PlannedShipmentLine | dict[str, Any]],
        initial_batches: pd.DataFrame,
        destinations: pd.DataFrame,
        skus: pd.DataFrame,
        lanes: pd.DataFrame,
        origin_date: str,
        inbound_shipments: Optional[pd.DataFrame] = None,
        destination_batches: Optional[pd.DataFrame] = None,
        lane_pruning_k: int = 3,
        warehouses: Optional[pd.DataFrame] = None,
    ) -> VerificationResult:
        """
        Independently evaluate plan lines against constraints C1–C5.
        Zero violations are required for plan acceptance.
        """
        violations: list[ConstraintViolation] = []
        checked_counts: dict[str, int] = {
            "C1_BATCH_STOCK": 0,
            "C2_ELIGIBILITY": 0,
            "C3_DEST_CAPACITY": 0,
            "C4_NON_NEGATIVE_INT": 0,
            "C5_LANE": 0,
        }

        # Handle empty plan lines
        if not plan_lines:
            return VerificationResult(
                passed=True,
                total_violations=0,
                violations=[],
                checked_rules_summary=checked_counts,
            )

        # Normalize lines to standard dict representation
        normalized_lines: list[dict[str, Any]] = []
        for line in plan_lines:
            if isinstance(line, dict):
                normalized_lines.append(line)
            else:
                normalized_lines.append({
                    "line_id": getattr(line, "line_id", ""),
                    "warehouse_id": str(getattr(line, "warehouse_id", "")),
                    "batch_id": str(getattr(line, "batch_id", "")),
                    "sku_id": str(getattr(line, "sku_id", "")),
                    "dest_id": str(getattr(line, "dest_id", "")),
                    "quantity": getattr(line, "quantity", 0),
                    "arrival_date": str(getattr(line, "arrival_date", "")),
                    "remaining_life_at_arrival": getattr(line, "remaining_life_at_arrival", 0),
                    "min_required_life": getattr(line, "min_required_life", 0),
                })

        # Parse reference date
        parsed_origin = date.fromisoformat(str(origin_date)[:10])

        # ── Pre-process Raw Data for Independent Checking ─────────────────────

        # SKUs lookup
        sku_lookup: dict[str, dict[str, Any]] = {}
        for _, row in skus.iterrows():
            s_id = str(row["sku_id"])
            sku_lookup[s_id] = {
                "min_life_days": int(row.get("min_life_days", 0)),
                "unit_volume": float(row.get("unit_volume", 1.0)),
                "unit_cost": float(row.get("unit_cost", 10.0)),
                "unit_margin": float(row.get("unit_margin", 5.0)),
            }

        # Destinations lookup
        dest_capacity: dict[str, float] = {}
        for _, row in destinations.iterrows():
            d_id = str(row["dest_id"])
            dest_capacity[d_id] = float(row.get("storage_capacity", 99999.0))

        # Warehouses lookup
        known_whs: set[str] = set()
        if warehouses is not None and not warehouses.empty:
            wh_col = "warehouse_id" if "warehouse_id" in warehouses.columns else "location_id"
            if wh_col in warehouses.columns:
                known_whs = set(warehouses[wh_col].astype(str))

        # Lanes lookup: (warehouse_id, dest_id) -> info
        lane_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for _, row in lanes.iterrows():
            w_id = str(row.get("warehouse_id") or row.get("origin_warehouse_id") or "")
            d_id = str(row["dest_id"])
            lane_lookup[(w_id, d_id)] = {
                "transit_days": int(row.get("transit_days", 1)),
                "freight_rate": float(row.get("freight_rate", 1.0)),
                "blocked": bool(row.get("blocked", False)),
            }

        # Initial warehouse batches lookup: batch_id -> {location_id, sku_id, quantity, expiry_date}
        wh_batches = initial_batches
        if "location_type" in initial_batches.columns:
            wh_batches = initial_batches[initial_batches["location_type"] == "warehouse"]

        batch_lookup: dict[str, dict[str, Any]] = {}
        for _, row in wh_batches.iterrows():
            b_id = str(row["batch_id"])
            batch_lookup[b_id] = {
                "warehouse_id": str(row.get("location_id") or row.get("warehouse_id")),
                "sku_id": str(row["sku_id"]),
                "quantity": float(row["quantity"]),
                "expiry_date": date.fromisoformat(str(row["expiry_date"])[:10]),
            }

        # ── C4: Non-negative integer quantities ───────────────────────────────
        for line in normalized_lines:
            checked_counts["C4_NON_NEGATIVE_INT"] += 1
            qty = line["quantity"]
            line_id = line["line_id"]
            
            # Check integer type and whole number
            is_int = isinstance(qty, (int, float)) and float(qty).is_integer()
            if not is_int:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C4_NON_NEGATIVE_INT",
                        entity_id=line_id,
                        violation_message=f"Line {line_id} quantity {qty} is not an integer",
                        observed_value=float(qty) if isinstance(qty, (int, float)) else -1.0,
                        limit_value=1.0,
                    )
                )
            elif qty <= 0:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C4_NON_NEGATIVE_INT",
                        entity_id=line_id,
                        violation_message=f"Line {line_id} quantity {qty} must be strictly positive",
                        observed_value=float(qty),
                        limit_value=1.0,
                    )
                )

        # ── C1: Batch Stock Availability ──────────────────────────────────────
        batch_allocated_qty: dict[str, float] = {}
        for line in normalized_lines:
            b_id = line["batch_id"]
            batch_allocated_qty[b_id] = batch_allocated_qty.get(b_id, 0.0) + float(line["quantity"])

        for b_id, total_alloc in batch_allocated_qty.items():
            checked_counts["C1_BATCH_STOCK"] += 1
            if b_id not in batch_lookup:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C1_BATCH_STOCK",
                        entity_id=b_id,
                        violation_message=f"Batch {b_id} does not exist in initial warehouse inventory",
                        observed_value=total_alloc,
                        limit_value=0.0,
                    )
                )
            else:
                avail_qty = batch_lookup[b_id]["quantity"]
                # 1e-6 numerical tolerance for floating comparison
                if total_alloc > avail_qty + 1e-6:
                    violations.append(
                        ConstraintViolation(
                            constraint_id="C1_BATCH_STOCK",
                            entity_id=b_id,
                            violation_message=(
                                f"Batch {b_id} allocation of {total_alloc:.1f} units "
                                f"exceeds available stock {avail_qty:.1f}"
                            ),
                            observed_value=total_alloc,
                            limit_value=avail_qty,
                        )
                    )

        # ── C2: Shelf-life and Lane Eligibility ───────────────────────────────
        for line in normalized_lines:
            checked_counts["C2_ELIGIBILITY"] += 1
            b_id = line["batch_id"]
            w_id = line["warehouse_id"]
            d_id = line["dest_id"]
            s_id = line["sku_id"]
            line_id = line["line_id"]

            # Unknown SKU check
            if s_id not in sku_lookup:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=s_id,
                        violation_message=f"Line {line_id} SKU {s_id} does not exist in SKUs master",
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )

            # Unknown Warehouse check
            if known_whs and w_id not in known_whs:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=w_id,
                        violation_message=f"Line {line_id} warehouse {w_id} does not exist in warehouses master",
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )

            if b_id not in batch_lookup:
                # Already captured in C1, but eligibility also fails
                continue

            b_info = batch_lookup[b_id]
            batch_wh = b_info["warehouse_id"]
            batch_sku = b_info["sku_id"]
            batch_expiry = b_info["expiry_date"]

            # Warehouse location match
            if batch_wh != w_id:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=line_id,
                        violation_message=(
                            f"Line {line_id} warehouse {w_id} does not match "
                            f"batch {b_id} actual warehouse {batch_wh}"
                        ),
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )

            # SKU match
            if batch_sku != s_id:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=line_id,
                        violation_message=(
                            f"Line {line_id} SKU {s_id} does not match "
                            f"batch {b_id} actual SKU {batch_sku}"
                        ),
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )

            # Expiry before origin date
            if batch_expiry <= parsed_origin:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=b_id,
                        violation_message=(
                            f"Batch {b_id} expiry {batch_expiry.isoformat()} is on or before "
                            f"planning origin date {parsed_origin.isoformat()}"
                        ),
                        observed_value=float((batch_expiry - parsed_origin).days),
                        limit_value=1.0,
                    )
                )

            # Lane lookup
            lane_key = (w_id, d_id)
            if lane_key not in lane_lookup:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=f"{w_id}->{d_id}",
                        violation_message=f"Lane {w_id} -> {d_id} does not exist in lanes network",
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )
                continue

            lane_info = lane_lookup[lane_key]
            if lane_info["blocked"]:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=f"{w_id}->{d_id}",
                        violation_message=f"Lane {w_id} -> {d_id} is blocked",
                        observed_value=1.0,
                        limit_value=0.0,
                    )
                )

            # Shelf-life arrival check
            transit_days = lane_info["transit_days"]
            arrival_date = parsed_origin + pd.Timedelta(days=transit_days)
            if isinstance(arrival_date, pd.Timestamp):
                arrival_date = arrival_date.date()
            remaining_life_at_arr = (batch_expiry - arrival_date).days

            # Arrival date consistency & format check
            line_arr_raw = str(line.get("arrival_date", "")).strip()[:10]
            if line_arr_raw:
                try:
                    parsed_line_arr = date.fromisoformat(line_arr_raw)
                    if parsed_line_arr != arrival_date:
                        violations.append(
                            ConstraintViolation(
                                constraint_id="C2_ELIGIBILITY",
                                entity_id=line_id,
                                violation_message=(
                                    f"Line {line_id} arrival date '{line_arr_raw}' does not match expected arrival "
                                    f"date {arrival_date.isoformat()} (origin {parsed_origin.isoformat()} + {transit_days} transit days)"
                                ),
                                observed_value=float((parsed_line_arr - parsed_origin).days),
                                limit_value=float(transit_days),
                            )
                        )
                except ValueError:
                    violations.append(
                        ConstraintViolation(
                            constraint_id="C2_ELIGIBILITY",
                            entity_id=line_id,
                            violation_message=f"Line {line_id} arrival date '{line_arr_raw}' has invalid date format",
                            observed_value=1.0,
                            limit_value=0.0,
                        )
                    )

            min_life = sku_lookup.get(s_id, {}).get("min_life_days", 0)
            if remaining_life_at_arr < min_life:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C2_ELIGIBILITY",
                        entity_id=b_id,
                        violation_message=(
                            f"Batch {b_id} remaining life at arrival ({remaining_life_at_arr} days on {arrival_date}) "
                            f"is below required minimum life ({min_life} days) for SKU {s_id}"
                        ),
                        observed_value=float(remaining_life_at_arr),
                        limit_value=float(min_life),
                    )
                )

        # ── C3: Destination Storage Capacity ──────────────────────────────────
        # Independent calculation of destination capRoom:
        # Existing lots at destination from destination_batches or initial_batches (location_type == 'destination')
        # plus inbound shipments
        dest_lots_df = get_destination_lots(
            origin_date=parsed_origin,
            horizon_days=7,
            batches_df=destination_batches if destination_batches is not None else initial_batches,
            inbound_df=inbound_shipments,
        )

        dest_used_vol: dict[str, float] = {}
        if not dest_lots_df.empty:
            for _, row in dest_lots_df.iterrows():
                d_id = str(row["dest_id"])
                s_id = str(row["sku_id"])
                u_vol = sku_lookup.get(s_id, {}).get("unit_volume", 1.0)
                qty = float(row.get("quantity", 0.0))
                dest_used_vol[d_id] = dest_used_vol.get(d_id, 0.0) + (qty * u_vol)

        cap_room: dict[str, float] = {}
        for d_id, cap in dest_capacity.items():
            used = dest_used_vol.get(d_id, 0.0)
            cap_room[d_id] = max(0.0, cap - used)

        dest_allocated_vol: dict[str, float] = {}
        for line in normalized_lines:
            d_id = line["dest_id"]
            s_id = line["sku_id"]
            qty = float(line["quantity"])
            u_vol = sku_lookup.get(s_id, {}).get("unit_volume", 1.0)
            dest_allocated_vol[d_id] = dest_allocated_vol.get(d_id, 0.0) + (qty * u_vol)

        for d_id, alloc_vol in dest_allocated_vol.items():
            checked_counts["C3_DEST_CAPACITY"] += 1
            if d_id not in dest_capacity:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C3_DEST_CAPACITY",
                        entity_id=d_id,
                        violation_message=f"Destination {d_id} does not exist in destinations master",
                        observed_value=alloc_vol,
                        limit_value=0.0,
                    )
                )
                continue

            room = cap_room.get(d_id, 0.0)
            if alloc_vol > room + 1e-6:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C3_DEST_CAPACITY",
                        entity_id=d_id,
                        violation_message=(
                            f"Destination {d_id} allocated volume {alloc_vol:.2f} m3 "
                            f"exceeds available capacity room {room:.2f} m3"
                        ),
                        observed_value=alloc_vol,
                        limit_value=room,
                    )
                )

        # ── C5: Lane Pruning Policy ───────────────────────────────────────────
        # For each (dest_id, sku_id):
        # 1. Distinct warehouses used in plan_lines <= lane_pruning_k
        # 2. Each used warehouse must be among the top k eligible warehouses by freight_rate
        dest_sku_warehouses: dict[tuple[str, str], set[str]] = {}
        for line in normalized_lines:
            key = (line["dest_id"], line["sku_id"])
            if key not in dest_sku_warehouses:
                dest_sku_warehouses[key] = set()
            dest_sku_warehouses[key].add(line["warehouse_id"])

        # Compute all eligible pairs independently using filter_eligible_lane_batches
        elig_df = filter_eligible_lane_batches(
            origin_date=parsed_origin,
            batches_df=initial_batches,
            lanes_df=lanes,
            skus_df=skus,
        )
        valid_elig = elig_df[elig_df["is_eligible"]].copy() if not elig_df.empty else pd.DataFrame()

        for (d_id, s_id), used_whs in dest_sku_warehouses.items():
            checked_counts["C5_LANE"] += 1
            if len(used_whs) > lane_pruning_k:
                violations.append(
                    ConstraintViolation(
                        constraint_id="C5_LANE",
                        entity_id=f"({d_id},{s_id})",
                        violation_message=(
                            f"Destination {d_id} SKU {s_id} served from {len(used_whs)} warehouses, "
                            f"exceeding lane pruning limit of {lane_pruning_k}"
                        ),
                        observed_value=float(len(used_whs)),
                        limit_value=float(lane_pruning_k),
                    )
                )

            # Check if all used warehouses are among top k lowest-freight eligible warehouses
            sub_elig = valid_elig[(valid_elig["dest_id"] == d_id) & (valid_elig["sku_id"] == s_id)]
            if not sub_elig.empty:
                sorted_whs = (
                    sub_elig.sort_values(by="freight_rate")["warehouse_id"]
                    .drop_duplicates()
                    .tolist()[:lane_pruning_k]
                )
                for w in used_whs:
                    if w not in sorted_whs:
                        violations.append(
                            ConstraintViolation(
                                constraint_id="C5_LANE",
                                entity_id=f"({d_id},{s_id},{w})",
                                violation_message=(
                                    f"Warehouse {w} is not among the top {lane_pruning_k} "
                                    f"lowest-freight eligible warehouses for ({d_id}, {s_id})"
                                ),
                                observed_value=1.0,
                                limit_value=0.0,
                            )
                        )

        total_violations = len(violations)
        return VerificationResult(
            passed=(total_violations == 0),
            total_violations=total_violations,
            violations=violations,
            checked_rules_summary=checked_counts,
        )
