"""
Optiqo — Linear Programming Allocation Model Assembly (PRD §5.1 P0-05, §10.2, §10.3, §10.5)

Builds the lot-by-lot continuous linear program:
- Variables:
  - x(b, l) >= 0: Whole units shipped from batch b to destination l.
  - Auxiliary: short(l, s, k), waste(l, s, k), end(l, s, k), wc(l, s, k, j) >= 0.
- Hard Constraints:
  - C1: Batch stock availability: sum_l x(b, l) <= Q_b
  - C2: Lane and shelf-life eligibility: r(b, l) >= m_s, unblocked
  - C3: Destination capacity: sum_s vol_s * sum_{b in s} x(b, l) <= capRoom(l)
  - C4: Post-processed via conservative round-down
  - C5: Lane pruning: max k lowest-freight warehouses per (dest, SKU)
- Lot-by-lot expiry logic (PRD §10.3) per destination-SKU and demand scenario.
- Solves via PuLP (or SciPy HiGHS backend when host lacks standalone CBC binaries).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
import pulp
from scipy.optimize import linprog

from backend.core.logging import get_logger
from backend.engines.protocols import OptimizerConfig
from backend.services.inventory import (
    filter_eligible_lane_batches,
    get_destination_lots,
)

logger = get_logger(__name__)


class LPModelResult:
    """Raw solver output from the linear program."""

    def __init__(
        self,
        status: str,
        objective_value: float,
        solver_runtime_seconds: float,
        allocations: dict[tuple[str, str], float],
        unmet_demand: dict[tuple[str, str, str], float],
        expected_expiry: dict[tuple[str, str, str], float],
        slack_data: dict[str, Any],
        eligible_pairs_df: pd.DataFrame,
        batch_quantities: dict[str, float],
        dest_capacity_rooms: dict[str, float],
    ):
        self.status = status
        self.objective_value = objective_value
        self.solver_runtime_seconds = solver_runtime_seconds
        self.allocations = allocations
        self.unmet_demand = unmet_demand
        self.expected_expiry = expected_expiry
        self.slack_data = slack_data
        self.eligible_pairs_df = eligible_pairs_df
        self.batch_quantities = batch_quantities
        self.dest_capacity_rooms = dest_capacity_rooms


def solve_lp_via_scipy(
    c: np.ndarray,
    A_ub: np.ndarray,
    b_ub: np.ndarray,
    bounds: list[tuple[float, float | None]],
    timeout_seconds: int = 60,
) -> tuple[str, float, np.ndarray]:
    """
    Solve linear program using SciPy's HiGHS solver.
    """
    try:
        res = linprog(
            c=c,
            A_ub=A_ub if len(A_ub) > 0 else None,
            b_ub=b_ub if len(b_ub) > 0 else None,
            bounds=bounds,
            method="highs",
            options={"time_limit": timeout_seconds, "disp": False},
        )
        if res.success:
            return "OPTIMAL", float(res.fun), res.x
        elif res.status == 1:
            return "SOLVER_TIMEOUT", float(res.fun or 0.0), res.x if res.x is not None else np.zeros(len(c))
        elif res.status == 2:
            return "INFEASIBLE", 0.0, np.zeros(len(c))
        else:
            return "ERROR", 0.0, np.zeros(len(c))
    except Exception as exc:
        logger.error("SciPy HiGHS solver failed: %s", exc)
        return "ERROR", 0.0, np.zeros(len(c))


def build_and_solve_lp(
    usable_inventory: pd.DataFrame,
    forecast_table: pd.DataFrame,
    destinations: pd.DataFrame,
    skus: pd.DataFrame,
    lanes: pd.DataFrame,
    config: OptimizerConfig,
    origin_date: Optional[str] = None,
    destination_lots_df: Optional[pd.DataFrame] = None,
) -> LPModelResult:
    """
    Build and solve the lot-by-lot allocation LP.
    """
    start_time = time.time()
    parsed_origin = date.fromisoformat(origin_date) if origin_date else date(2024, 1, 15)
    horizon_days = 7

    # 1. Evaluate batch-lane eligibility (Hard Constraint C2)
    eligible_pairs = filter_eligible_lane_batches(
        origin_date=parsed_origin,
        batches_df=usable_inventory,
        lanes_df=lanes,
        skus_df=skus,
    )

    if eligible_pairs.empty or not eligible_pairs["is_eligible"].any():
        runtime = round(time.time() - start_time, 3)
        return LPModelResult(
            status="OPTIMAL",
            objective_value=0.0,
            solver_runtime_seconds=runtime,
            allocations={},
            unmet_demand={},
            expected_expiry={},
            slack_data={"empty_eligible_pairs": True},
            eligible_pairs_df=pd.DataFrame(),
            batch_quantities={},
            dest_capacity_rooms={},
        )

    eligible_df = eligible_pairs[eligible_pairs["is_eligible"]].copy()

    # 2. Lane pruning (Hard Constraint C5):
    # For each (dest_id, sku_id), keep at most k lowest-freight warehouses
    k_prune = config.lane_pruning_k
    pruned_rows = []
    for (d_id, s_id), group in eligible_df.groupby(["dest_id", "sku_id"]):
        # Sort by freight_rate ascending
        sorted_g = group.sort_values(by="freight_rate")
        unique_whs = sorted_g["warehouse_id"].drop_duplicates().tolist()[:k_prune]
        pruned_rows.append(sorted_g[sorted_g["warehouse_id"].isin(unique_whs)])

    if pruned_rows:
        eligible_df = pd.concat(pruned_rows, ignore_index=True)

    # 3. Destination capacity calculation (Hard Constraint C3)
    dest_caps = dict(zip(
        destinations["dest_id"].astype(str),
        pd.to_numeric(destinations["storage_capacity"], errors="coerce").fillna(99999.0)
    ))
    sku_volumes = dict(zip(
        skus["sku_id"].astype(str),
        pd.to_numeric(skus["unit_volume"], errors="coerce").fillna(1.0)
    ))
    sku_margins = dict(zip(
        skus["sku_id"].astype(str),
        pd.to_numeric(skus["unit_margin"], errors="coerce").fillna(5.0)
    ))
    sku_costs = dict(zip(
        skus["sku_id"].astype(str),
        pd.to_numeric(skus["unit_cost"], errors="coerce").fillna(10.0)
    ))

    # Existing destination volume
    if destination_lots_df is None:
        destination_lots_df = get_destination_lots(
            origin_date=parsed_origin,
            horizon_days=horizon_days,
            batches_df=usable_inventory,
        )

    dest_existing_vol: dict[str, float] = {}
    if not destination_lots_df.empty:
        for _, row in destination_lots_df.iterrows():
            d_id = str(row["dest_id"])
            s_id = str(row["sku_id"])
            vol = sku_volumes.get(s_id, 1.0)
            dest_existing_vol[d_id] = dest_existing_vol.get(d_id, 0.0) + (float(row["quantity"]) * vol)

    cap_room: dict[str, float] = {}
    for d_id, cap in dest_caps.items():
        used = dest_existing_vol.get(d_id, 0.0)
        cap_room[d_id] = max(0.0, cap - used)

    # Batch quantities (Hard Constraint C1)
    batch_quantities: dict[str, float] = {}
    for _, row in eligible_df.iterrows():
        b_id = str(row["batch_id"])
        if b_id not in batch_quantities:
            batch_quantities[b_id] = float(row["quantity"])

    # 4. Scenarios and Forecasts per (dest_id, sku_id)
    scenarios = ["low", "mid", "high"]
    scenario_weights = {"low": 0.3, "mid": 0.4, "high": 0.3}

    # Demand lookup from forecast_table
    demand_lookup: dict[tuple[str, str, str], float] = {}
    for _, row in forecast_table.iterrows():
        d_id = str(row["dest_id"])
        s_id = str(row["sku_id"])
        demand_lookup[(d_id, s_id, "low")] = float(row.get("low_horizon_demand", 0.0) or 0.0)
        demand_lookup[(d_id, s_id, "mid")] = float(row.get("mid_horizon_demand", 0.0) or 0.0)
        demand_lookup[(d_id, s_id, "high")] = float(row.get("high_horizon_demand", 0.0) or 0.0)

    # Destination lots grouped by (dest_id, sku_id)
    dest_lots_grouped: dict[tuple[str, str], list[dict]] = {}
    if not destination_lots_df.empty:
        for _, row in destination_lots_df.iterrows():
            key = (str(row["dest_id"]), str(row["sku_id"]))
            if key not in dest_lots_grouped:
                dest_lots_grouped[key] = []
            dest_lots_grouped[key].append(row.to_dict())

    # 5. Assemble LP Variables and Constraints
    # Variable indices:
    # x(b, l) for (b, l) in eligible_df
    # short(l, s, k), waste(l, s, k), end(l, s, k)
    # wc(l, s, k, j) for lots j with n_j <= horizon_days

    pair_keys = [
        (str(row["batch_id"]), str(row["dest_id"]))
        for _, row in eligible_df.iterrows()
    ]
    # Remove duplicates if any
    pair_keys = list(dict.fromkeys(pair_keys))

    var_map: dict[str, int] = {}
    var_bounds: list[tuple[float, float | None]] = []
    c_coeffs: list[float] = []

    def get_var_idx(name: str, cost: float = 0.0, lb: float = 0.0, ub: float | None = None) -> int:
        if name not in var_map:
            idx = len(var_map)
            var_map[name] = idx
            var_bounds.append((lb, ub))
            c_coeffs.append(cost)
        return var_map[name]

    # Freight cost per shipment pair
    pair_info_map = {
        (str(row["batch_id"]), str(row["dest_id"])): row.to_dict()
        for _, row in eligible_df.iterrows()
    }

    for (b_id, d_id) in pair_keys:
        info = pair_info_map[(b_id, d_id)]
        s_id = str(info["sku_id"])
        vol = sku_volumes.get(s_id, 1.0)
        fr = float(info.get("freight_rate", 1.0) or 1.0)
        unit_freight = fr * vol
        get_var_idx(f"x__{b_id}__{d_id}", cost=unit_freight, lb=0.0)

    # Unique active (dest_id, sku_id) pairs
    active_dest_skus = sorted(list(set(
        (str(row["dest_id"]), str(row["sku_id"]))
        for _, row in eligible_df.iterrows()
    )))

    # Auxiliary variables per scenario
    for (d_id, s_id) in active_dest_skus:
        margin = sku_margins.get(s_id, 5.0)
        cost_v = sku_costs.get(s_id, 10.0)
        p_short = config.shortage_penalty_factor * margin
        v_waste = cost_v
        h_end = config.holding_cost_rate * cost_v

        for k in scenarios:
            weight = scenario_weights[k]
            get_var_idx(f"short__{d_id}__{s_id}__{k}", cost=weight * p_short, lb=0.0)
            get_var_idx(f"waste__{d_id}__{s_id}__{k}", cost=weight * v_waste, lb=0.0)
            get_var_idx(f"end__{d_id}__{s_id}__{k}", cost=weight * h_end, lb=0.0)

    A_ub_rows: list[list[float]] = []
    b_ub_vals: list[float] = []

    def add_le_constraint(row_dict: dict[int, float], rhs: float):
        row = [0.0] * len(var_map)
        for idx, val in row_dict.items():
            row[idx] = val
        A_ub_rows.append(row)
        b_ub_vals.append(rhs)

    # ── Constraint C1: Batch stock availability ──────────────────────────────
    # sum_l x(b, l) <= Q_b
    batch_pairs: dict[str, list[str]] = {}
    for (b_id, d_id) in pair_keys:
        if b_id not in batch_pairs:
            batch_pairs[b_id] = []
        batch_pairs[b_id].append(d_id)

    for b_id, dest_list in batch_pairs.items():
        q_b = batch_quantities.get(b_id, 0.0)
        row_dict = {var_map[f"x__{b_id}__{d_id}"]: 1.0 for d_id in dest_list}
        add_le_constraint(row_dict, q_b)

    # ── Constraint C3: Destination storage capacity ──────────────────────────
    # sum_s vol_s * sum_b x(b, l) <= capRoom(l)
    dest_pairs: dict[str, list[tuple[str, str]]] = {}
    for (b_id, d_id) in pair_keys:
        if d_id not in dest_pairs:
            dest_pairs[d_id] = []
        dest_pairs[d_id].append((b_id, d_id))

    for d_id, p_list in dest_pairs.items():
        room = cap_room.get(d_id, 99999.0)
        row_dict = {}
        for (b_id, _) in p_list:
            s_id = str(pair_info_map[(b_id, d_id)]["sku_id"])
            vol = sku_volumes.get(s_id, 1.0)
            v_idx = var_map[f"x__{b_id}__{d_id}"]
            row_dict[v_idx] = row_dict.get(v_idx, 0.0) + vol
        add_le_constraint(row_dict, room)

    # ── Constraints: Expiry, Unmet Demand, and Ending Inventory ──────────────
    for (d_id, s_id) in active_dest_skus:
        # Destination lots
        existing_lots = dest_lots_grouped.get((d_id, s_id), [])
        total_existing = sum(float(l["quantity"]) for l in existing_lots)

        # Candidate shipped batches to this dest-SKU
        dest_batches = [
            (b_id, int(pair_info_map[(b_id, d_id)]["remaining_life_at_arrival"]))
            for (b_id, _) in dest_pairs.get(d_id, [])
            if str(pair_info_map[(b_id, d_id)]["sku_id"]) == s_id
        ]

        for k in scenarios:
            D_k_H = demand_lookup.get((d_id, s_id, k), 0.0)
            short_idx = var_map[f"short__{d_id}__{s_id}__{k}"]
            waste_idx = var_map[f"waste__{d_id}__{s_id}__{k}"]
            end_idx = var_map[f"end__{d_id}__{s_id}__{k}"]

            # 1. Unmet demand constraint:
            # short >= D_k(H) - (S_total - waste)
            # -short - S_total + waste <= -D_k(H)
            # -short - (total_existing + sum x) + waste <= -D_k(H)
            # -short - sum x + waste <= -D_k(H) + total_existing
            row_short = {short_idx: -1.0, waste_idx: 1.0}
            for (b_id, _) in dest_batches:
                v_idx = var_map[f"x__{b_id}__{d_id}"]
                row_short[v_idx] = row_short.get(v_idx, 0.0) - 1.0
            add_le_constraint(row_short, -D_k_H + total_existing)

            # 2. Ending stock constraint:
            # end >= S_total - waste - D_k(H) + short
            # -end + S_total - waste + short <= D_k(H)
            # -end + sum x - waste + short <= D_k(H) - total_existing
            row_end = {end_idx: -1.0, waste_idx: -1.0, short_idx: 1.0}
            for (b_id, _) in dest_batches:
                v_idx = var_map[f"x__{b_id}__{d_id}"]
                row_end[v_idx] = row_end.get(v_idx, 0.0) + 1.0
            add_le_constraint(row_end, D_k_H - total_existing)

            # 3. Lot-by-lot expiry logic (PRD §10.3):
            # For lots expiring with n_j <= horizon_days:
            # waste >= cumulative_stock_j - D_k(n_j)
            expiring_existing = [l for l in existing_lots if l.get("expiry_day_index", 99) <= horizon_days]
            expiring_shipped = [(b, n) for (b, n) in dest_batches if n <= horizon_days]

            if expiring_existing or expiring_shipped:
                # Event horizons in days
                n_events = sorted(list(set(
                    [l["expiry_day_index"] for l in expiring_existing] +
                    [n for (_, n) in expiring_shipped]
                )))

                cum_exist = 0.0
                for n_j in n_events:
                    cum_exist += sum(float(l["quantity"]) for l in expiring_existing if l["expiry_day_index"] == n_j)
                    D_k_n = (n_j / float(horizon_days)) * D_k_H

                    # waste >= cum_exist + sum_{b with n_b <= n_j} x(b, l) - D_k_n
                    # -waste + sum x <= D_k_n - cum_exist
                    row_w = {waste_idx: -1.0}
                    for (b_id, n_b) in expiring_shipped:
                        if n_b <= n_j:
                            v_idx = var_map[f"x__{b_id}__{d_id}"]
                            row_w[v_idx] = row_w.get(v_idx, 0.0) + 1.0
                    add_le_constraint(row_w, D_k_n - cum_exist)

    # 6. Execute Solve
    c_arr = np.array(c_coeffs, dtype=float)
    # Ensure all constraint rows match total variable count
    n_vars = len(var_map)
    for r in A_ub_rows:
        if len(r) < n_vars:
            r.extend([0.0] * (n_vars - len(r)))

    A_ub_mat = np.array(A_ub_rows, dtype=float) if A_ub_rows else np.empty((0, n_vars))
    b_ub_arr = np.array(b_ub_vals, dtype=float) if b_ub_vals else np.empty(0)

    status, obj_val, sol_vec = solve_lp_via_scipy(
        c=c_arr,
        A_ub=A_ub_mat,
        b_ub=b_ub_arr,
        bounds=var_bounds,
        timeout_seconds=config.solver_timeout_seconds,
    )

    runtime = round(time.time() - start_time, 3)

    # Extract allocations
    allocations: dict[tuple[str, str], float] = {}
    for (b_id, d_id) in pair_keys:
        var_name = f"x__{b_id}__{d_id}"
        if var_name in var_map:
            val = float(sol_vec[var_map[var_name]])
            if val > 1e-4:
                allocations[(b_id, d_id)] = val

    # Extract unmet and expiry
    unmet_demand: dict[tuple[str, str, str], float] = {}
    expected_expiry: dict[tuple[str, str, str], float] = {}

    for (d_id, s_id) in active_dest_skus:
        for k in scenarios:
            s_name = f"short__{d_id}__{s_id}__{k}"
            w_name = f"waste__{d_id}__{s_id}__{k}"
            if s_name in var_map:
                unmet_demand[(d_id, s_id, k)] = float(sol_vec[var_map[s_name]])
            if w_name in var_map:
                expected_expiry[(d_id, s_id, k)] = float(sol_vec[var_map[w_name]])

    # Slack data
    slack_data: dict[str, Any] = {
        "num_variables": n_vars,
        "num_constraints": len(b_ub_vals),
        "total_shipped_continuous": sum(allocations.values()),
    }

    logger.info(
        "LP solver complete: status=%s, obj=%.2f, runtime=%.3fs, active_lines=%d",
        status, obj_val, runtime, len(allocations),
    )

    return LPModelResult(
        status=status,
        objective_value=obj_val,
        solver_runtime_seconds=runtime,
        allocations=allocations,
        unmet_demand=unmet_demand,
        expected_expiry=expected_expiry,
        slack_data=slack_data,
        eligible_pairs_df=eligible_df,
        batch_quantities=batch_quantities,
        dest_capacity_rooms=cap_room,
    )
