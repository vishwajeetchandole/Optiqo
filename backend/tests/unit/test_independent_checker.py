"""
Optiqo — Independent Constraint Verifier Unit Tests (PRD §5.1 P0-06, §7.4 O1, Plan §5.3)

Tests independent verification of operational hard constraints C1–C5:
- C1: Batch stock availability
- C2: Shelf-life & lane eligibility
- C3: Destination capacity room
- C4: Positive whole integer allocations
- C5: Lane pruning policy
- Multiple simultaneous violations
- Deliberately corrupted plans
"""

from __future__ import annotations

from datetime import date
import pytest
import pandas as pd

from backend.engines.protocols import PlannedShipmentLine
from backend.engines.verification.checker import ConstraintVerifier


@pytest.fixture
def base_network_data():
    """Small deterministic test fixture for independent constraint verification."""
    skus = pd.DataFrame([
        {
            "sku_id": "SKU_01",
            "name": "Product 1",
            "category": "Dairy",
            "shelf_life_days": 30,
            "min_life_days": 10,
            "unit_volume": 0.05,
            "unit_cost": 20.0,
            "unit_margin": 10.0,
        },
        {
            "sku_id": "SKU_02",
            "name": "Product 2",
            "category": "Snacks",
            "shelf_life_days": 90,
            "min_life_days": 20,
            "unit_volume": 0.02,
            "unit_cost": 15.0,
            "unit_margin": 8.0,
        },
    ])

    destinations = pd.DataFrame([
        {
            "dest_id": "DEST_01",
            "name": "Store 1",
            "type": "store",
            "region": "North",
            "storage_capacity": 50.0,  # m3
        },
        {
            "dest_id": "DEST_02",
            "name": "Store 2",
            "type": "store",
            "region": "South",
            "storage_capacity": 5.0,   # Small capacity
        },
    ])

    lanes = pd.DataFrame([
        {
            "warehouse_id": "WH_01",
            "dest_id": "DEST_01",
            "distance_km": 100,
            "transit_days": 2,
            "freight_rate": 1.0,
            "blocked": False,
        },
        {
            "warehouse_id": "WH_02",
            "dest_id": "DEST_01",
            "distance_km": 150,
            "transit_days": 3,
            "freight_rate": 1.5,
            "blocked": False,
        },
        {
            "warehouse_id": "WH_03",
            "dest_id": "DEST_01",
            "distance_km": 200,
            "transit_days": 4,
            "freight_rate": 2.0,
            "blocked": False,
        },
        {
            "warehouse_id": "WH_04",
            "dest_id": "DEST_01",
            "distance_km": 300,
            "transit_days": 5,
            "freight_rate": 3.0,
            "blocked": False,
        },
        {
            "warehouse_id": "WH_01",
            "dest_id": "DEST_02",
            "distance_km": 200,
            "transit_days": 2,
            "freight_rate": 1.2,
            "blocked": False,
        },
        {
            "warehouse_id": "WH_02",
            "dest_id": "DEST_02",
            "distance_km": 250,
            "transit_days": 3,
            "freight_rate": 1.8,
            "blocked": True,  # Blocked lane
        },
    ])

    # Initial inventory: warehouse batches + destination stock
    initial_batches = pd.DataFrame([
        {
            "location_id": "WH_01",
            "sku_id": "SKU_01",
            "batch_id": "B_WH1_01",
            "location_type": "warehouse",
            "quantity": 100,
            "expiry_date": "2026-11-20",  # ~27 days life
        },
        {
            "location_id": "WH_01",
            "sku_id": "SKU_02",
            "batch_id": "B_WH1_02",
            "location_type": "warehouse",
            "quantity": 200,
            "expiry_date": "2026-12-15",
        },
        {
            "location_id": "WH_02",
            "sku_id": "SKU_01",
            "batch_id": "B_WH2_01",
            "location_type": "warehouse",
            "quantity": 150,
            "expiry_date": "2026-11-25",
        },
        {
            "location_id": "WH_03",
            "sku_id": "SKU_01",
            "batch_id": "B_WH3_01",
            "location_type": "warehouse",
            "quantity": 120,
            "expiry_date": "2026-11-28",
        },
        {
            "location_id": "WH_04",
            "sku_id": "SKU_01",
            "batch_id": "B_WH4_01",
            "location_type": "warehouse",
            "quantity": 80,
            "expiry_date": "2026-11-30",
        },
        # Expired batch
        {
            "location_id": "WH_01",
            "sku_id": "SKU_01",
            "batch_id": "B_WH1_EXP",
            "location_type": "warehouse",
            "quantity": 50,
            "expiry_date": "2026-10-20",  # Expired before 2026-10-24
        },
        # Insufficient shelf life at arrival (transit=2d, arrival=10-26, expiry=10-30 -> 4d life < 10d min)
        {
            "location_id": "WH_01",
            "sku_id": "SKU_01",
            "batch_id": "B_WH1_SHORTLIFE",
            "location_type": "warehouse",
            "quantity": 60,
            "expiry_date": "2026-10-30",
        },
        # Destination on-hand stock
        {
            "location_id": "DEST_02",
            "sku_id": "SKU_01",
            "batch_id": "B_DEST2_01",
            "location_type": "destination",
            "quantity": 80,  # 80 * 0.05 = 4.0 m3 used (capacity 5.0 m3 -> room 1.0 m3)
            "expiry_date": "2026-11-15",
        },
    ])

    warehouses = pd.DataFrame([
        {"warehouse_id": "WH_01", "name": "Main DC"},
        {"warehouse_id": "WH_02", "name": "East DC"},
        {"warehouse_id": "WH_03", "name": "West DC"},
        {"warehouse_id": "WH_04", "name": "South DC"},
    ])

    return {
        "skus": skus,
        "destinations": destinations,
        "lanes": lanes,
        "warehouses": warehouses,
        "initial_batches": initial_batches,
        "origin_date": "2026-10-24",
    }


def make_valid_line(
    line_id="L1",
    warehouse_id="WH_01",
    batch_id="B_WH1_01",
    sku_id="SKU_01",
    dest_id="DEST_01",
    quantity=50,
    arrival_date="2026-10-26",
    remaining_life=25,
    min_required_life=10,
    unit_freight=0.05,
    total_freight=2.5,
):
    return PlannedShipmentLine(
        line_id=line_id,
        warehouse_id=warehouse_id,
        batch_id=batch_id,
        sku_id=sku_id,
        dest_id=dest_id,
        quantity=quantity,
        arrival_date=arrival_date,
        remaining_life_at_arrival=remaining_life,
        min_required_life=min_required_life,
        unit_freight_cost=unit_freight,
        total_freight_cost=total_freight,
        batch_fully_allocated=False,
        destination_capacity_binding=False,
        next_best_warehouse_id="WH_02",
        next_best_freight_cost=0.075,
    )


class TestIndependentConstraintVerifier:
    def test_valid_plan_passes_verification(self, base_network_data):
        verifier = ConstraintVerifier()
        valid_lines = [
            make_valid_line(line_id="L1", quantity=40),
            make_valid_line(line_id="L2", batch_id="B_WH1_02", sku_id="SKU_02", quantity=60),
        ]

        result = verifier.verify_plan(
            plan_lines=valid_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is True
        assert result.total_violations == 0
        assert len(result.violations) == 0

    def test_empty_plan_passes_verification(self, base_network_data):
        verifier = ConstraintVerifier()
        result = verifier.verify_plan(
            plan_lines=[],
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is True
        assert result.total_violations == 0

    def test_c1_violation_exceeded_batch_stock(self, base_network_data):
        """Batch B_WH1_01 has 100 units; allocating 120 must trigger C1."""
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", batch_id="B_WH1_01", quantity=120)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c1_violations = [v for v in result.violations if v.constraint_id == "C1_BATCH_STOCK"]
        assert len(c1_violations) >= 1
        assert c1_violations[0].entity_id == "B_WH1_01"
        assert c1_violations[0].observed_value == 120.0
        assert c1_violations[0].limit_value == 100.0

    def test_c1_violation_across_multiple_lines(self, base_network_data):
        """Batch B_WH1_01 has 100 units; two lines of 60 each (sum 120) must trigger C1."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", batch_id="B_WH1_01", dest_id="DEST_01", quantity=60),
            make_valid_line("L2", batch_id="B_WH1_01", dest_id="DEST_01", quantity=60),
        ]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c1_violations = [v for v in result.violations if v.constraint_id == "C1_BATCH_STOCK"]
        assert len(c1_violations) >= 1
        assert c1_violations[0].observed_value == 120.0

    def test_c1_violation_nonexistent_batch(self, base_network_data):
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", batch_id="B_NONEXISTENT", quantity=10)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c1_violations = [v for v in result.violations if v.constraint_id == "C1_BATCH_STOCK"]
        assert len(c1_violations) >= 1

    def test_c2_violation_expired_batch(self, base_network_data):
        """Batch B_WH1_EXP expired on 2026-10-20 before origin date 2026-10-24."""
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", batch_id="B_WH1_EXP", quantity=10)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert len(c2_violations) >= 1

    def test_c2_violation_insufficient_shelf_life(self, base_network_data):
        """Batch B_WH1_SHORTLIFE has 4 days remaining at arrival vs 10 days required."""
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", batch_id="B_WH1_SHORTLIFE", quantity=10)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("below required minimum life" in v.violation_message for v in c2_violations)

    def test_c2_violation_blocked_lane(self, base_network_data):
        """Lane WH_02 -> DEST_02 is blocked."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line(
                "L1",
                warehouse_id="WH_02",
                batch_id="B_WH2_01",
                dest_id="DEST_02",
                quantity=10,
            )
        ]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("blocked" in v.violation_message for v in c2_violations)

    def test_c3_violation_destination_capacity_exceeded(self, base_network_data):
        """DEST_02 capacity is 5.0 m3. Destination already holds 80 units of SKU_01 (4.0 m3).
        Allocating 30 units (1.5 m3) results in total used volume 5.5 m3 > 5.0 m3 capacity room."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line(
                "L1",
                warehouse_id="WH_01",
                batch_id="B_WH1_01",
                dest_id="DEST_02",
                sku_id="SKU_01",
                quantity=30,  # 30 * 0.05 = 1.5 m3 > 1.0 m3 room
            )
        ]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c3_violations = [v for v in result.violations if v.constraint_id == "C3_DEST_CAPACITY"]
        assert len(c3_violations) >= 1
        assert c3_violations[0].entity_id == "DEST_02"
        assert c3_violations[0].observed_value == 1.5
        assert c3_violations[0].limit_value == 1.0

    def test_c4_violation_fractional_allocation(self, base_network_data):
        """Shipment line with quantity=15.5 must trigger C4."""
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", quantity=15.5)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c4_violations = [v for v in result.violations if v.constraint_id == "C4_NON_NEGATIVE_INT"]
        assert len(c4_violations) >= 1
        assert "not an integer" in c4_violations[0].violation_message

    def test_c4_violation_negative_or_zero_quantity(self, base_network_data):
        verifier = ConstraintVerifier()
        corrupted_lines = [make_valid_line("L1", quantity=0)]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        c4_violations = [v for v in result.violations if v.constraint_id == "C4_NON_NEGATIVE_INT"]
        assert len(c4_violations) >= 1

    def test_c5_violation_more_than_k_warehouses(self, base_network_data):
        """Serving DEST_01 SKU_01 from 4 warehouses when k=3 must trigger C5."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", warehouse_id="WH_01", batch_id="B_WH1_01", quantity=10),
            make_valid_line("L2", warehouse_id="WH_02", batch_id="B_WH2_01", quantity=10),
            make_valid_line("L3", warehouse_id="WH_03", batch_id="B_WH3_01", quantity=10),
            make_valid_line("L4", warehouse_id="WH_04", batch_id="B_WH4_01", quantity=10),
        ]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
            lane_pruning_k=3,
        )

        assert result.passed is False
        c5_violations = [v for v in result.violations if v.constraint_id == "C5_LANE"]
        assert len(c5_violations) >= 1

    def test_multiple_simultaneous_violations_detected(self, base_network_data):
        """Plan with C1 (batch exceeded), C4 (fractional), and C2 (blocked lane)."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            # C1 + C4
            make_valid_line("L1", batch_id="B_WH1_01", quantity=150.5),
            # C2 (blocked lane)
            make_valid_line("L2", warehouse_id="WH_02", batch_id="B_WH2_01", dest_id="DEST_02", quantity=10),
        ]

        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )

        assert result.passed is False
        violation_types = {v.constraint_id for v in result.violations}
        assert "C1_BATCH_STOCK" in violation_types
        assert "C2_ELIGIBILITY" in violation_types
        assert "C4_NON_NEGATIVE_INT" in violation_types
        assert len(result.violations) >= 3

    def test_c2_violation_unknown_sku(self, base_network_data):
        """Fabricated SKU identifier not in SKUs catalog must trigger C2."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", sku_id="SKU_FABRICATED", quantity=10),
        ]
        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("SKU SKU_FABRICATED does not exist" in v.violation_message for v in c2_violations)

    def test_c3_violation_unknown_destination(self, base_network_data):
        """Fabricated destination identifier not in destinations catalog must trigger C3."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", dest_id="DEST_FABRICATED", quantity=10),
        ]
        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is False
        c3_violations = [v for v in result.violations if v.constraint_id == "C3_DEST_CAPACITY"]
        assert any("Destination DEST_FABRICATED does not exist" in v.violation_message for v in c3_violations)

    def test_c2_violation_unknown_warehouse(self, base_network_data):
        """Fabricated warehouse identifier not in warehouses catalog must trigger C2."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", warehouse_id="WH_FABRICATED", quantity=10),
        ]
        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            warehouses=base_network_data["warehouses"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("warehouse WH_FABRICATED does not exist" in v.violation_message for v in c2_violations)

    def test_c2_violation_mismatched_arrival_date(self, base_network_data):
        """Arrival date claiming 2026-10-30 when transit is 2 days from 2026-10-24 must trigger C2."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", arrival_date="2026-10-30", quantity=10),
        ]
        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("does not match expected arrival date" in v.violation_message for v in c2_violations)

    def test_c2_violation_invalid_arrival_date_format(self, base_network_data):
        """Unparseable arrival date string must trigger C2."""
        verifier = ConstraintVerifier()
        corrupted_lines = [
            make_valid_line("L1", arrival_date="bad-date-string", quantity=10),
        ]
        result = verifier.verify_plan(
            plan_lines=corrupted_lines,
            initial_batches=base_network_data["initial_batches"],
            destinations=base_network_data["destinations"],
            skus=base_network_data["skus"],
            lanes=base_network_data["lanes"],
            origin_date=base_network_data["origin_date"],
        )
        assert result.passed is False
        c2_violations = [v for v in result.violations if v.constraint_id == "C2_ELIGIBILITY"]
        assert any("invalid date format" in v.violation_message for v in c2_violations)
