"""
Optiqo — Integration Tests: Fault Injection Scenarios (PRD §5.1, §7.4, §11.2, §14 N1/N8, §16.1 E6, Metric S3/S4)

Verifies:
1. Seeded 13-fault injection on dataset blocks planning and backtest with HTTP 422 VALIDATION_FAILED.
2. Injected solver failures (infeasibility, timeout) produce honest RFC 7807 errors without fabricating plans.
3. Injected constraint violations (C1-C5) are caught by independent verifier, marking status UNVERIFIED
   without bypassing constraint verification or run auditing.
4. Formula injection neutralization in CSV exports (PRD §14 N8).
5. Missing datasets and malformed inputs return structured RFC 7807 problem details.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.core.exceptions import InfeasibleError, SolverTimeoutError
from backend.engines.protocols import (
    ConstraintViolation,
    OptimizerEngineOutput,
    PlannedShipmentLine,
    VerificationResult,
)
from backend.engines.verification.checker import ConstraintVerifier
from backend.main import app
from backend.schemas.plan import PlanRequest
from backend.services.orchestrator import run_planning_cycle
from backend.storage.exporter import export_run_artifact


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── Scenario 1: Seeded Dataset Fault Injection (PRD §16.1 E6, Metric S3) ───────

class TestDatasetFaultInjection:
    """Verifies that dataset faults block planning and backtest with HTTP 422 VALIDATION_FAILED."""

    def test_fault_negative_inventory_blocks_planning(self, corrupted_dataset_dir: Path, api_client: TestClient):
        # Corrupt inventory_batches.csv with negative quantity
        inv_file = corrupted_dataset_dir / "inventory_batches.csv"
        df = pd.read_csv(inv_file)
        df.loc[0, "quantity"] = -50
        df.to_csv(inv_file, index=False)

        # Plan request should fail with 422
        resp = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "dataset_path": str(corrupted_dataset_dir),
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_FAILED" or "Validation" in body["title"]
        assert "negative" in str(body).lower() or "inventory_batches" in str(body).lower()

    def test_fault_invalid_transit_days_blocks_backtest(self, corrupted_dataset_dir: Path, api_client: TestClient):
        # Corrupt lanes.csv with transit_days = 0
        lanes_file = corrupted_dataset_dir / "lanes.csv"
        df = pd.read_csv(lanes_file)
        df.loc[0, "transit_days"] = 0
        df.to_csv(lanes_file, index=False)

        # Backtest request should fail with 422
        resp = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(corrupted_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_FAILED" or "Validation" in body["title"]
        assert "transit" in str(body).lower() or "lanes" in str(body).lower()

    def test_fault_missing_required_file_blocks_planning(self, corrupted_dataset_dir: Path, api_client: TestClient):
        # Delete skus.csv
        skus_file = corrupted_dataset_dir / "skus.csv"
        if skus_file.exists():
            skus_file.unlink()

        resp = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "dataset_path": str(corrupted_dataset_dir),
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_FAILED" or "Validation" in body["title"]
        assert "skus" in str(body).lower()

    def test_fault_negative_capacity_detected_in_validation_endpoint(
        self, corrupted_dataset_dir: Path, api_client: TestClient
    ):
        # Corrupt destinations.csv with storage_capacity = -10.0
        dest_file = corrupted_dataset_dir / "destinations.csv"
        df = pd.read_csv(dest_file)
        df.loc[0, "storage_capacity"] = -10.0
        df.to_csv(dest_file, index=False)

        resp = api_client.post(
            "/api/data/validate",
            json={
                "dataset_path": str(corrupted_dataset_dir),
                "planning_date": "2024-01-15",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "INVALID"
        assert body["planning_blocked"] is True
        assert any("capacity" in str(e).lower() or "storage" in str(e).lower() for e in body["errors"])


# ── Scenario 2: Optimizer Fault Injection & Honest Failure Handling ───────────

class TestOptimizerFaultInjection:
    """Verifies that optimizer failures do not produce fabricated fallback plans."""

    def test_infeasible_lp_raises_rfc7807_error(self, clean_dataset_dir: Path):
        """When LP solver returns INFEASIBLE, run_planning_cycle raises InfeasibleError."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize_allocation.return_value = OptimizerEngineOutput(
            status="INFEASIBLE",
            objective_value=0.0,
            solver_runtime_seconds=0.5,
            lines=[],
            rounding_loss_units=0,
            unmet_demand_by_dest_sku=pd.DataFrame(),
            expected_expiry_by_dest_sku=pd.DataFrame(),
            slack_data={},
        )

        req = PlanRequest(
            origin_date="2024-01-15",
            dataset_path=str(clean_dataset_dir),
        )

        with pytest.raises(InfeasibleError) as exc_info:
            run_planning_cycle(req, optimizer=mock_optimizer)

        assert exc_info.value.http_status == 422
        assert exc_info.value.error_code == "INFEASIBLE"

    def test_solver_timeout_raises_rfc7807_error(self, clean_dataset_dir: Path):
        """When LP solver returns SOLVER_TIMEOUT with no feasible solution, raises SolverTimeoutError."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize_allocation.return_value = OptimizerEngineOutput(
            status="SOLVER_TIMEOUT",
            objective_value=0.0,
            solver_runtime_seconds=60.1,
            lines=[],
            rounding_loss_units=0,
            unmet_demand_by_dest_sku=pd.DataFrame(),
            expected_expiry_by_dest_sku=pd.DataFrame(),
            slack_data={},
        )

        req = PlanRequest(
            origin_date="2024-01-15",
            dataset_path=str(clean_dataset_dir),
        )

        with pytest.raises(SolverTimeoutError) as exc_info:
            run_planning_cycle(req, optimizer=mock_optimizer)

        assert exc_info.value.http_status == 500
        assert exc_info.value.error_code == "SOLVER_TIMEOUT"


# ── Scenario 3: Constraint Verifier Fault Injection & Safe Auditing ─────────────

class TestConstraintVerifierFaultInjection:
    """
    Verifies that deliberate constraint violations (C1-C5) are caught by independent verifier,
    resulting in status UNVERIFIED and persisting the run manifest without bypassing auditing.
    """

    def test_independent_verifier_catches_injected_violations(self):
        verifier = ConstraintVerifier()

        # Synthetic network
        skus = pd.DataFrame([
            {"sku_id": "SKU_01", "name": "Prod 1", "category": "Dairy", "shelf_life_days": 30, "min_life_days": 10, "unit_volume": 0.05, "unit_cost": 20.0, "unit_margin": 10.0}
        ])
        destinations = pd.DataFrame([
            {"dest_id": "DEST_01", "name": "Store 1", "type": "store", "region": "North", "storage_capacity": 10.0}
        ])
        lanes = pd.DataFrame([
            {"warehouse_id": "WH_01", "origin_warehouse_id": "WH_01", "dest_id": "DEST_01", "distance_km": 100, "transit_days": 2, "freight_rate": 2.0}
        ])
        batches = pd.DataFrame([
            {"batch_id": "B_01", "warehouse_id": "WH_01", "sku_id": "SKU_01", "quantity": 100, "production_date": "2024-01-01", "expiry_date": "2024-01-31", "location_type": "warehouse"}
        ])

        # Fault 1: C1 Exceeded Batch Stock (allocate 200 units from batch of 100)
        line_c1 = PlannedShipmentLine(
            line_id="L1", warehouse_id="WH_01", batch_id="B_01", sku_id="SKU_01", dest_id="DEST_01",
            quantity=200, arrival_date="2024-01-17", remaining_life_at_arrival=14, min_required_life=10,
            unit_freight_cost=2.0, total_freight_cost=400.0, batch_fully_allocated=True,
            destination_capacity_binding=False, next_best_warehouse_id=None, next_best_freight_cost=None,
        )
        res = verifier.verify_plan([line_c1], batches, destinations, skus, lanes, origin_date="2024-01-15")
        assert res.passed is False
        assert any(v.constraint_id == "C1_BATCH_STOCK" for v in res.violations)

        # Fault 2: C2 Expired / Ineligible Batch (remaining life 5 < min 10)
        line_c2 = PlannedShipmentLine(
            line_id="L2", warehouse_id="WH_01", batch_id="B_01", sku_id="SKU_01", dest_id="DEST_01",
            quantity=50, arrival_date="2024-01-28", remaining_life_at_arrival=3, min_required_life=10,
            unit_freight_cost=2.0, total_freight_cost=100.0, batch_fully_allocated=False,
            destination_capacity_binding=False, next_best_warehouse_id=None, next_best_freight_cost=None,
        )
        res = verifier.verify_plan([line_c2], batches, destinations, skus, lanes, origin_date="2024-01-26")
        assert res.passed is False
        assert any(v.constraint_id == "C2_ELIGIBILITY" for v in res.violations)

        # Fault 3: C3 Destination Capacity Overflow (500 units * 0.05m3 = 25m3 > capacity 10m3)
        line_c3 = PlannedShipmentLine(
            line_id="L3", warehouse_id="WH_01", batch_id="B_01", sku_id="SKU_01", dest_id="DEST_01",
            quantity=500, arrival_date="2024-01-17", remaining_life_at_arrival=14, min_required_life=10,
            unit_freight_cost=2.0, total_freight_cost=1000.0, batch_fully_allocated=False,
            destination_capacity_binding=True, next_best_warehouse_id=None, next_best_freight_cost=None,
        )
        batches_large = batches.copy()
        batches_large.loc[0, "quantity"] = 1000
        res = verifier.verify_plan([line_c3], batches_large, destinations, skus, lanes, origin_date="2024-01-15")
        assert res.passed is False
        assert any(v.constraint_id == "C3_DEST_CAPACITY" for v in res.violations)

        # Fault 4: C4 Negative Quantity
        line_c4 = PlannedShipmentLine(
            line_id="L4", warehouse_id="WH_01", batch_id="B_01", sku_id="SKU_01", dest_id="DEST_01",
            quantity=-10, arrival_date="2024-01-17", remaining_life_at_arrival=14, min_required_life=10,
            unit_freight_cost=2.0, total_freight_cost=-20.0, batch_fully_allocated=False,
            destination_capacity_binding=False, next_best_warehouse_id=None, next_best_freight_cost=None,
        )
        res = verifier.verify_plan([line_c4], batches, destinations, skus, lanes, origin_date="2024-01-15")
        assert res.passed is False
        assert any(v.constraint_id == "C4_NON_NEGATIVE_INT" for v in res.violations)

        # Fault 5: C5 Unserviced Lane
        line_c5 = PlannedShipmentLine(
            line_id="L5", warehouse_id="WH_99", batch_id="B_01", sku_id="SKU_01", dest_id="DEST_01",
            quantity=10, arrival_date="2024-01-17", remaining_life_at_arrival=14, min_required_life=10,
            unit_freight_cost=2.0, total_freight_cost=20.0, batch_fully_allocated=False,
            destination_capacity_binding=False, next_best_warehouse_id=None, next_best_freight_cost=None,
        )
        res = verifier.verify_plan([line_c5], batches, destinations, skus, lanes, origin_date="2024-01-15")
        assert res.passed is False
        assert any(v.constraint_id == "C5_LANE" for v in res.violations)

    def test_pipeline_marks_unverified_and_preserves_audit_manifest(self, clean_dataset_dir: Path):
        """
        When solver output produces constraint violations, run_planning_cycle:
        1. Sets plan status to 'UNVERIFIED'
        2. checker_status.passed is False
        3. Persists run manifest with status UNVERIFIED and recorded violations for audit.
        """
        from backend.storage.repository import get_run

        mock_verifier = MagicMock()
        mock_verifier.verify_plan.return_value = VerificationResult(
            passed=False,
            total_violations=2,
            violations=[
                ConstraintViolation(
                    constraint_id="C1_BATCH_STOCK",
                    entity_id="B_01",
                    violation_message="Allocated 150 > stock 100",
                    observed_value=150.0,
                    limit_value=100.0,
                ),
                ConstraintViolation(
                    constraint_id="C3_DEST_CAPACITY",
                    entity_id="DEST_01",
                    violation_message="Destination storage capacity exceeded",
                    observed_value=55.0,
                    limit_value=50.0,
                ),
            ],
            checked_rules_summary={"C1_BATCH_STOCK": 1, "C3_DEST_CAPACITY": 1},
        )

        req = PlanRequest(
            origin_date="2024-01-15",
            dataset_path=str(clean_dataset_dir),
        )

        plan = run_planning_cycle(req, verifier=mock_verifier)

        # 1. Status is UNVERIFIED
        assert plan.status == "UNVERIFIED"
        assert plan.checker_status.passed is False
        assert plan.checker_status.violations_count == 2

        # 2. Audit manifest was persisted
        saved_manifest = get_run(plan.run_id)
        assert saved_manifest is not None
        assert saved_manifest["status"] == "UNVERIFIED"
        assert saved_manifest["checker_verdict"]["passed"] is False
        assert len(saved_manifest["checker_verdict"]["violations"]) == 2


# ── Scenario 4: Formula Injection Neutralization (PRD §14 N8) ─────────────────

class TestFormulaInjectionNeutralization:
    """Verifies that malicious formulas are escaped with single quote in exported CSVs."""

    def test_malicious_cells_are_neutralized_in_exported_csv(self):
        malicious_manifest = {
            "run_id": "test_injection_run",
            "run_type": "PLAN",
            "origin_date": "2024-01-15",
            "status": "OK",
            "plan_lines": [
                {
                    "line_id": "L1",
                    "warehouse_id": "=cmd|' /C calc'!A0",  # Malicious formula 1
                    "batch_id": "+100+200",               # Malicious formula 2
                    "sku_id": "@SUM(A1:A10)",             # Malicious formula 3
                    "dest_id": "-5*2",                    # Malicious formula 4
                    "quantity": 100,                      # Authentic integer
                    "arrival_date": "2024-01-18",
                    "remaining_life_at_arrival": 30,
                    "min_required_life": 10,
                    "unit_freight_cost": 2.5,             # Authentic float
                    "total_freight_cost": 250.0,
                    "explanation": {
                        "sentence": "=HYPERLINK(\"http://evil.com\")",
                    },
                }
            ],
        }

        csv_content, media_type = export_run_artifact(malicious_manifest, artifact="plan", format="csv")
        assert media_type == "text/csv"
        reader = csv.DictReader(io.StringIO(csv_content))
        row = next(reader)

        # Starting characters '=', '+', '-', '@' must be neutralized with leading single quote
        assert row["warehouse_id"].startswith("'="), f"Expected neutralized formula, got {row['warehouse_id']}"
        assert row["batch_id"].startswith("'+"), f"Expected neutralized formula, got {row['batch_id']}"
        assert row["sku_id"].startswith("'@"), f"Expected neutralized formula, got {row['sku_id']}"
        assert row["dest_id"].startswith("'-"), f"Expected neutralized formula, got {row['dest_id']}"
        assert row["explanation_sentence"].startswith("'="), f"Expected neutralized formula, got {row['explanation_sentence']}"

        # Real numbers must remain intact
        assert float(row["total_freight_cost"]) == 250.0
        assert int(row["quantity"]) == 100
