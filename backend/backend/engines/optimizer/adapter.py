"""
Optiqo — Allocation Optimizer Adapter (PRD §5.1 P0-05, Plan §5.2)

Implements OptimizerProtocol:
- Builds continuous LP lot-by-lot allocation model.
- Solves linear program via PuLP/HiGHS.
- Applies conservative integer round-down post-processing (C4).
- Tracks rounding loss, slacks, and outputs PlannedShipmentLine list.
- Returns OptimizerEngineOutput.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backend.core.logging import get_logger
from backend.engines.optimizer.lp_builder import build_and_solve_lp
from backend.engines.optimizer.rounding import (
    construct_shipment_lines,
    round_down_allocations,
)
from backend.engines.protocols import (
    OptimizerConfig,
    OptimizerEngineOutput,
    OptimizerProtocol,
)

logger = get_logger(__name__)


class OptimizerAdapter(OptimizerProtocol):
    """Reference implementation of OptimizerProtocol satisfying PRD §10.2, §10.3, §10.5."""

    def optimize_allocation(
        self,
        usable_inventory: pd.DataFrame,
        forecast_table: pd.DataFrame,
        destinations: pd.DataFrame,
        skus: pd.DataFrame,
        lanes: pd.DataFrame,
        config: OptimizerConfig,
        origin_date: Optional[str] = None,
    ) -> OptimizerEngineOutput:
        # 1. Build and solve linear program
        lp_result = build_and_solve_lp(
            usable_inventory=usable_inventory,
            forecast_table=forecast_table,
            destinations=destinations,
            skus=skus,
            lanes=lanes,
            config=config,
            origin_date=origin_date,
        )

        # 2. Integer round-down post-processing (C4)
        rounded_allocations, rounding_loss = round_down_allocations(lp_result.allocations)

        # 3. Assemble shipment lines
        shipment_lines = construct_shipment_lines(
            rounded_allocations=rounded_allocations,
            eligible_pairs_df=lp_result.eligible_pairs_df,
            batch_quantities=lp_result.batch_quantities,
            dest_capacity_rooms=lp_result.dest_capacity_rooms,
        )

        # 4. Tabulate unmet demand and expiry
        unmet_records = [
            {"dest_id": d, "sku_id": s, "scenario": k, "unmet_units": round(val, 2)}
            for (d, s, k), val in lp_result.unmet_demand.items()
        ]
        unmet_df = pd.DataFrame(unmet_records) if unmet_records else pd.DataFrame(columns=["dest_id", "sku_id", "scenario", "unmet_units"])

        expiry_records = [
            {"dest_id": d, "sku_id": s, "scenario": k, "expected_expiry_units": round(val, 2)}
            for (d, s, k), val in lp_result.expected_expiry.items()
        ]
        expiry_df = pd.DataFrame(expiry_records) if expiry_records else pd.DataFrame(columns=["dest_id", "sku_id", "scenario", "expected_expiry_units"])

        # Augment slack data
        slack_summary = lp_result.slack_data.copy()
        slack_summary["rounding_loss_units"] = rounding_loss
        slack_summary["total_shipped_integer_units"] = sum(rounded_allocations.values())
        slack_summary["active_shipment_lines_count"] = len(shipment_lines)

        logger.info(
            "OptimizerAdapter finished: status=%s, lines=%d, integer_units=%d, rounding_loss=%d",
            lp_result.status, len(shipment_lines), sum(rounded_allocations.values()), rounding_loss,
        )

        return OptimizerEngineOutput(
            status=lp_result.status,
            objective_value=round(lp_result.objective_value, 2),
            solver_runtime_seconds=lp_result.solver_runtime_seconds,
            lines=shipment_lines,
            rounding_loss_units=rounding_loss,
            unmet_demand_by_dest_sku=unmet_df,
            expected_expiry_by_dest_sku=expiry_df,
            slack_data=slack_summary,
        )
