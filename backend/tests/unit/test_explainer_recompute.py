"""
Optiqo — Grounded Explanation Numerical Recomputation Tests (PRD §5.1 P0-08, §10.9, §7.4 O3)

Verifies:
1. 100% coverage of all plan lines with explanations.
2. 100% numerical match between explanation sentences, evidence dictionaries, and raw underlying tables.
3. Zero hallucinated metrics, savings, or certainty claims.
"""

from __future__ import annotations

import re
import pytest
import pandas as pd

from backend.engines.protocols import PlannedShipmentLine
from backend.services.explainer import generate_plan_explanations


@pytest.fixture
def explainer_fixture():
    skus = pd.DataFrame([
        {
            "sku_id": "SKU_01",
            "name": "Dairy 1",
            "category": "Dairy",
            "shelf_life_days": 30,
            "min_life_days": 10,
            "unit_volume": 0.05,
            "unit_cost": 20.0,
            "unit_margin": 10.0,
        },
        {
            "sku_id": "SKU_02",
            "name": "Snack 2",
            "category": "Snacks",
            "shelf_life_days": 90,
            "min_life_days": 15,
            "unit_volume": 0.02,
            "unit_cost": 15.0,
            "unit_margin": 8.0,
        },
    ])

    destinations = pd.DataFrame([
        {"dest_id": "DEST_01", "name": "Store 1", "storage_capacity": 50.0},
        {"dest_id": "DEST_02", "name": "Store 2", "storage_capacity": 30.0},
    ])

    lanes = pd.DataFrame([
        {"warehouse_id": "WH_01", "dest_id": "DEST_01", "distance_km": 100, "transit_days": 2, "freight_rate": 1.0, "blocked": False},
        {"warehouse_id": "WH_02", "dest_id": "DEST_01", "distance_km": 150, "transit_days": 3, "freight_rate": 1.5, "blocked": False},
        {"warehouse_id": "WH_01", "dest_id": "DEST_02", "distance_km": 200, "transit_days": 2, "freight_rate": 1.2, "blocked": False},
    ])

    initial_batches = pd.DataFrame([
        # Warehouse stock
        {"location_id": "WH_01", "sku_id": "SKU_01", "batch_id": "B_WH1_01", "location_type": "warehouse", "quantity": 100, "expiry_date": "2026-11-20"},
        {"location_id": "WH_01", "sku_id": "SKU_02", "batch_id": "B_WH1_02", "location_type": "warehouse", "quantity": 200, "expiry_date": "2026-12-15"},
        # Destination current stock
        {"location_id": "DEST_01", "sku_id": "SKU_01", "batch_id": "B_D1_01", "location_type": "destination", "quantity": 25, "expiry_date": "2026-11-10"},
        {"location_id": "DEST_02", "sku_id": "SKU_02", "batch_id": "B_D2_01", "location_type": "destination", "quantity": 10, "expiry_date": "2026-12-01"},
    ])

    forecast_table = pd.DataFrame([
        {"dest_id": "DEST_01", "sku_id": "SKU_01", "horizon_mean": 120.0, "low_horizon_demand": 95.0, "high_horizon_demand": 145.0},
        {"dest_id": "DEST_02", "sku_id": "SKU_02", "horizon_mean": 80.0, "low_horizon_demand": 60.0, "high_horizon_demand": 100.0},
    ])

    return {
        "skus": skus,
        "destinations": destinations,
        "lanes": lanes,
        "initial_batches": initial_batches,
        "forecast_table": forecast_table,
    }


class TestGroundedExplainer:
    def test_complete_explanation_coverage(self, explainer_fixture):
        """Every single plan line must receive a complete explanation object."""
        lines = [
            PlannedShipmentLine(
                line_id="L1",
                warehouse_id="WH_01",
                batch_id="B_WH1_01",
                sku_id="SKU_01",
                dest_id="DEST_01",
                quantity=80,
                arrival_date="2026-10-26",
                remaining_life_at_arrival=25,
                min_required_life=10,
                unit_freight_cost=0.05,
                total_freight_cost=4.00,
                batch_fully_allocated=False,
                destination_capacity_binding=False,
                next_best_warehouse_id="WH_02",
                next_best_freight_cost=0.075,
            ),
            PlannedShipmentLine(
                line_id="L2",
                warehouse_id="WH_01",
                batch_id="B_WH1_02",
                sku_id="SKU_02",
                dest_id="DEST_02",
                quantity=50,
                arrival_date="2026-10-26",
                remaining_life_at_arrival=50,
                min_required_life=15,
                unit_freight_cost=0.024,
                total_freight_cost=1.20,
                batch_fully_allocated=False,
                destination_capacity_binding=False,
                next_best_warehouse_id=None,
                next_best_freight_cost=None,
            ),
        ]

        items = generate_plan_explanations(
            plan_lines=lines,
            forecast_table=explainer_fixture["forecast_table"],
            initial_batches=explainer_fixture["initial_batches"],
            destinations=explainer_fixture["destinations"],
            skus=explainer_fixture["skus"],
            lanes=explainer_fixture["lanes"],
        )

        assert len(items) == len(lines)
        for idx, item in enumerate(items):
            assert item.line_id == lines[idx].line_id
            assert item.explanation is not None
            assert item.explanation.evidence is not None
            assert len(item.explanation.sentence) > 0

    def test_numerical_recomputation_with_savings_clause(self, explainer_fixture):
        """Sentence with next-best warehouse freight savings: all numbers must match 100%."""
        lines = [
            PlannedShipmentLine(
                line_id="L1",
                warehouse_id="WH_01",
                batch_id="B_WH1_01",
                sku_id="SKU_01",
                dest_id="DEST_01",
                quantity=80,
                arrival_date="2026-10-26",
                remaining_life_at_arrival=25,
                min_required_life=10,
                unit_freight_cost=0.05,
                total_freight_cost=4.00,
                batch_fully_allocated=False,
                destination_capacity_binding=False,
                next_best_warehouse_id="WH_02",
                next_best_freight_cost=0.075,
            )
        ]

        items = generate_plan_explanations(
            plan_lines=lines,
            forecast_table=explainer_fixture["forecast_table"],
            initial_batches=explainer_fixture["initial_batches"],
            destinations=explainer_fixture["destinations"],
            skus=explainer_fixture["skus"],
            lanes=explainer_fixture["lanes"],
        )

        item = items[0]
        ev = item.explanation.evidence
        sent = item.explanation.sentence

        # 1. Check evidence against raw input data
        # Forecast from forecast_table
        fc_row = explainer_fixture["forecast_table"][
            (explainer_fixture["forecast_table"]["dest_id"] == "DEST_01")
            & (explainer_fixture["forecast_table"]["sku_id"] == "SKU_01")
        ].iloc[0]
        assert ev.forecast_mean == float(fc_row["horizon_mean"])
        assert ev.forecast_range == [float(fc_row["low_horizon_demand"]), float(fc_row["high_horizon_demand"])]

        # Destination stock from initial_batches
        dest_stock = float(explainer_fixture["initial_batches"][
            (explainer_fixture["initial_batches"]["location_id"] == "DEST_01")
            & (explainer_fixture["initial_batches"]["sku_id"] == "SKU_01")
        ]["quantity"].sum())
        assert ev.current_stock == dest_stock

        # Shipped quantity
        assert ev.shipped_quantity == 80
        assert ev.remaining_shelf_life_arrival == 25
        assert ev.min_life_requirement == 10

        # Freight costs and savings
        assert ev.freight_cost_selected == 4.00
        expected_next_cost = round(0.075 * 80, 2)  # 6.00
        assert ev.freight_cost_next_best == expected_next_cost
        assert ev.next_best_warehouse == "WH_02"
        expected_saving = round(expected_next_cost - 4.00, 2)  # 2.00

        # 2. Check that sentence matches every single number in evidence
        # Sentence template:
        # "Shipped 80 units of SKU_01 from WH_01 (batch B_WH1_01, 25 days shelf life remaining vs 10 min required) to DEST_01 to cover 120 forecast units with current stock of 25, saving 2.00 in freight vs WH_02."
        assert f"Shipped {ev.shipped_quantity} units of SKU_01 from WH_01" in sent
        assert f"{ev.remaining_shelf_life_arrival} days shelf life remaining vs {ev.min_life_requirement} min required" in sent
        assert f"to cover {ev.forecast_mean:.0f} forecast units" in sent
        assert f"current stock of {ev.current_stock:.0f}" in sent
        assert f"saving {expected_saving:.2f} in freight vs WH_02" in sent

    def test_numerical_recomputation_without_next_best(self, explainer_fixture):
        """When no next-best warehouse is available, sentence terminates cleanly with 0 hallucinated savings."""
        lines = [
            PlannedShipmentLine(
                line_id="L2",
                warehouse_id="WH_01",
                batch_id="B_WH1_02",
                sku_id="SKU_02",
                dest_id="DEST_02",
                quantity=50,
                arrival_date="2026-10-26",
                remaining_life_at_arrival=50,
                min_required_life=15,
                unit_freight_cost=0.024,
                total_freight_cost=1.20,
                batch_fully_allocated=False,
                destination_capacity_binding=False,
                next_best_warehouse_id=None,
                next_best_freight_cost=None,
            )
        ]

        items = generate_plan_explanations(
            plan_lines=lines,
            forecast_table=explainer_fixture["forecast_table"],
            initial_batches=explainer_fixture["initial_batches"],
            destinations=explainer_fixture["destinations"],
            skus=explainer_fixture["skus"],
            lanes=explainer_fixture["lanes"],
        )

        item = items[0]
        ev = item.explanation.evidence
        sent = item.explanation.sentence

        assert ev.next_best_warehouse is None
        assert ev.freight_cost_next_best is None
        assert "saving" not in sent.lower()
        assert sent.endswith(f"current stock of {ev.current_stock:.0f}.")

    def test_batch_fully_allocated_flag(self, explainer_fixture):
        """Batch B_WH1_01 has 100 units. Allocating all 100 sets is_batch_fully_allocated to True."""
        lines = [
            PlannedShipmentLine(
                line_id="L1",
                warehouse_id="WH_01",
                batch_id="B_WH1_01",
                sku_id="SKU_01",
                dest_id="DEST_01",
                quantity=100,  # All 100 available units
                arrival_date="2026-10-26",
                remaining_life_at_arrival=25,
                min_required_life=10,
                unit_freight_cost=0.05,
                total_freight_cost=5.00,
                batch_fully_allocated=True,
                destination_capacity_binding=False,
                next_best_warehouse_id=None,
                next_best_freight_cost=None,
            )
        ]

        items = generate_plan_explanations(
            plan_lines=lines,
            forecast_table=explainer_fixture["forecast_table"],
            initial_batches=explainer_fixture["initial_batches"],
            destinations=explainer_fixture["destinations"],
            skus=explainer_fixture["skus"],
            lanes=explainer_fixture["lanes"],
        )

        assert items[0].explanation.evidence.is_batch_fully_allocated is True
