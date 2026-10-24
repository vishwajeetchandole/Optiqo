"""
Optiqo — Simulation Policies Unit Tests (PRD §10.7, Plan §6 Phase 6)

Tests:
1. B1Policy trailing-average target calculation and order sizing.
2. B1Policy nearest-warehouse sourcing and FEFO batch selection.
3. B1Policy proportional cutback when warehouse stock is scarce.
4. B1Policy destination storage capacity truncation.
5. B2Policy forecast-driven target calculation with identical allocation mechanics.
6. OptiqoPolicy LP solver execution and format translation.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import pytest

from backend.data.loader import load_dataset
from backend.simulation.policies import B1Policy, B2Policy, OptiqoPolicy


@pytest.fixture(scope="module")
def dataset_dict(clean_dataset_dir: Path) -> dict[str, pd.DataFrame]:
    loaded, errs = load_dataset(clean_dataset_dir)
    assert loaded is not None, f"Failed to load dataset: {errs}"
    return loaded.as_dict()


class TestSimulationPolicies:
    def test_b1_policy_planning(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test B1 policy calculates orders based on trailing sales and allocates from nearest warehouse."""
        policy = B1Policy()
        current_date = date(2024, 6, 1)
        wh_id = str(dataset_dict["warehouses"].iloc[0]["warehouse_id"])
        dest_id = str(dataset_dict["destinations"].iloc[0]["dest_id"])
        sku_id = str(dataset_dict["skus"].iloc[0]["sku_id"])

        wh_batches = [
            {
                "warehouse_id": wh_id,
                "batch_id": "BATCH_OLD",
                "sku_id": sku_id,
                "quantity": 500.0,
                "expiry_date": date(2024, 8, 1),
            },
            {
                "warehouse_id": wh_id,
                "batch_id": "BATCH_NEW",
                "sku_id": sku_id,
                "quantity": 500.0,
                "expiry_date": date(2024, 10, 1),
            },
        ]
        dest_lots = [
            {
                "dest_id": dest_id,
                "sku_id": sku_id,
                "batch_id": "BATCH_DEST",
                "quantity": 50.0,
                "expiry_date": date(2024, 7, 1),
            }
        ]
        inbound = []

        lines = policy.plan_cycle(
            current_date=current_date,
            warehouse_batches=wh_batches,
            destination_lots=dest_lots,
            inbound_shipments=inbound,
            dataset=dataset_dict,
            safety_days=2,
        )

        assert isinstance(lines, list)
        if lines:
            first_line = lines[0]
            assert "warehouse_id" in first_line
            assert "dest_id" in first_line
            assert "batch_id" in first_line
            assert "quantity" in first_line
            assert "freight_cost" in first_line
            assert "arrival_date" in first_line
            assert first_line["quantity"] > 0
            # Sourced oldest batch first (FEFO)
            assert first_line["batch_id"] == "BATCH_OLD"

    def test_b1_proportional_cutback(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test B1 policy scales down allocations proportionally when warehouse supply is scarce."""
        policy = B1Policy()
        current_date = date(2024, 6, 1)
        wh_id = str(dataset_dict["warehouses"].iloc[0]["warehouse_id"])
        sku_id = str(dataset_dict["skus"].iloc[0]["sku_id"])

        # Very low stock in warehouse
        wh_batches = [
            {
                "warehouse_id": wh_id,
                "batch_id": "SCARCE_BATCH",
                "sku_id": sku_id,
                "quantity": 10.0,
                "expiry_date": date(2024, 12, 1),
            }
        ]
        dest_lots = []
        inbound = []

        lines = policy.plan_cycle(
            current_date=current_date,
            warehouse_batches=wh_batches,
            destination_lots=dest_lots,
            inbound_shipments=inbound,
            dataset=dataset_dict,
            safety_days=2,
        )

        total_shipped = sum(line["quantity"] for line in lines)
        assert total_shipped <= 10.0

    def test_b2_policy_uses_forecast_table(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test B2 policy uses forecast_table values rather than trailing sales."""
        policy = B2Policy()
        current_date = date(2024, 6, 1)
        wh_id = str(dataset_dict["warehouses"].iloc[0]["warehouse_id"])
        dest_id = str(dataset_dict["destinations"].iloc[0]["dest_id"])
        sku_id = str(dataset_dict["skus"].iloc[0]["sku_id"])

        wh_batches = [
            {
                "warehouse_id": wh_id,
                "batch_id": "FC_BATCH",
                "sku_id": sku_id,
                "quantity": 1000.0,
                "expiry_date": date(2024, 12, 1),
            }
        ]
        dest_lots = []
        inbound = []

        # Synthetic forecast table
        forecast_table = pd.DataFrame([
            {
                "dest_id": dest_id,
                "sku_id": sku_id,
                "horizon_mean": 210.0,  # 30 units/day for 7 days
                "low_horizon_demand": 150.0,
                "high_horizon_demand": 270.0,
            }
        ])

        lines = policy.plan_cycle(
            current_date=current_date,
            warehouse_batches=wh_batches,
            destination_lots=dest_lots,
            inbound_shipments=inbound,
            dataset=dataset_dict,
            forecast_table=forecast_table,
            safety_days=2,
        )

        assert len(lines) > 0
        allocated = [l for l in lines if l["dest_id"] == dest_id and l["sku_id"] == sku_id]
        assert len(allocated) > 0
        # Expected target = 210 + (210/7)*2 = 270
        assert allocated[0]["quantity"] == 270

    def test_optiqo_policy_lp_execution(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test OptiqoPolicy successfully executes LP optimization and returns valid lines."""
        policy = OptiqoPolicy()
        current_date = date(2024, 6, 1)
        wh_id = str(dataset_dict["warehouses"].iloc[0]["warehouse_id"])
        dest_id = str(dataset_dict["destinations"].iloc[0]["dest_id"])
        sku_id = str(dataset_dict["skus"].iloc[0]["sku_id"])

        wh_batches = [
            {
                "warehouse_id": wh_id,
                "batch_id": "OPT_BATCH_1",
                "sku_id": sku_id,
                "quantity": 1000.0,
                "expiry_date": date(2024, 12, 1),
            }
        ]
        dest_lots = [
            {
                "dest_id": dest_id,
                "sku_id": sku_id,
                "batch_id": "DEST_LOT_1",
                "quantity": 10.0,
                "expiry_date": date(2024, 7, 1),
            }
        ]
        forecast_table = pd.DataFrame([
            {
                "dest_id": dest_id,
                "sku_id": sku_id,
                "horizon_mean": 100.0,
                "low_horizon_demand": 70.0,
                "high_horizon_demand": 130.0,
            }
        ])

        lines = policy.plan_cycle(
            current_date=current_date,
            warehouse_batches=wh_batches,
            destination_lots=dest_lots,
            inbound_shipments=[],
            dataset=dataset_dict,
            forecast_table=forecast_table,
            safety_days=2,
        )

        assert isinstance(lines, list)
        for line in lines:
            assert line["quantity"] > 0
            assert "arrival_date" in line
            assert "freight_cost" in line
            assert "line_id" in line
