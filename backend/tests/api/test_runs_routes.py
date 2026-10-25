"""
Optiqo — Run Storage & Export API Integration Tests (PRD §5.1 P0-11, §6.7, Plan §4.8, §4.9)

Tests:
1. Planning run via POST /api/plan automatically persists run manifest retrievable via GET /api/runs/{run_id}.
2. Backtest run via POST /api/backtest automatically persists run manifest.
3. GET /api/runs lists all persisted runs with summary metadata.
4. GET /api/runs/{run_id} returns full RunManifest schema.
5. GET /api/runs/{run_id} returns 404 for non-existent run_id.
6. GET /api/runs/{run_id}/export supports format=csv and format=json for plan, risks, and kpis.
7. GET /api/runs/{run_id}/export returns 422 for invalid format or invalid artifact.
8. GET /api/runs/{run_id}/export CSV response verifies formula-injection neutralization (PRD §14 N8).
"""

from __future__ import annotations

from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.storage.repository import compute_dataset_hash, save_run


class TestRunsAPI:
    def test_network_map_is_bound_to_plan_dataset_and_run(
        self, clean_dataset_dir: Path, api_client: TestClient
    ):
        run_id = f"network_map_api_test_{uuid.uuid4().hex}"
        run_file = save_run({
            "run_id": run_id,
            "run_type": "PLAN",
            "origin_date": "2024-01-15",
            "dataset_hash": compute_dataset_hash(clean_dataset_dir),
            "_dataset_path": str(clean_dataset_dir.resolve()),
            "parameters": {"horizon_days": 7},
            "checker_verdict": {"passed": True},
            "plan_lines": [{
                "line_id": "network-line-1",
                "warehouse_id": "WH_01",
                "dest_id": "DEST_001",
                "sku_id": "SKU_001",
                "quantity": 25,
                "freight_cost": 4.5,
            }],
            "risk_alerts": [{
                "dest_id": "DEST_001",
                "sku_id": "SKU_001",
                "severity": "HIGH",
                "financial_exposure": 12.0,
                "days_of_cover": 2.0,
                "expected_unmet_units": 5.0,
                "unmet_share_pct": 20.0,
                "expected_expiry_units": 0.0,
                "expected_expiry_loss_cost": 0.0,
                "excess_units": 0,
                "is_supply_shortage": False,
                "primary_driver": "Low cover.",
            }],
        })
        try:
            response = api_client.get(f"/api/runs/{run_id}/network")
            assert response.status_code == 200
            network = response.json()
            manifest_response = api_client.get(f"/api/runs/{run_id}")
            assert manifest_response.status_code == 200
            manifest = manifest_response.json()
            assert "_dataset_path" not in manifest
            assert network["run_id"] == run_id
            assert network["dataset_hash"] == manifest["dataset_hash"]
            assert len(network["locations"]) == 44
            assert all(location["coordinate_status"] == "missing" for location in network["locations"])
            assert network["flows"] == [{
                "line_id": "network-line-1",
                "source_id": "WH_01",
                "destination_id": "DEST_001",
                "sku_id": "SKU_001",
                "quantity": 25.0,
                "freight_cost": 4.5,
                "verification_status": "verified",
            }]
            destination = next(
                location for location in network["locations"]
                if location["id"] == "DEST_001"
            )
            assert destination["risk"] == {
                "basis": "pre-plan",
                "level": "HIGH",
                "alert_count": 1,
                "expected_unmet_units": 5.0,
                "expected_expiry_units": 0.0,
                "minimum_days_of_cover": 2.0,
                "primary_drivers": ["Low cover."],
            }
        finally:
            if run_file.exists():
                run_file.unlink()

    def test_network_map_rejects_backtest_run(self, api_client: TestClient):
        run_id = "network_backtest_run"
        save_run({
            "run_id": run_id,
            "run_type": "BACKTEST",
            "dataset_hash": "hash123",
        })
        response = api_client.get(f"/api/runs/{run_id}/network")
        assert response.status_code == 422

    def test_plan_persistence_and_retrieval(self, clean_dataset_dir: Path, api_client: TestClient):
        """Test POST /api/plan automatically creates a persisted run retrievable via GET /api/runs/{run_id}."""
        # 1. Execute plan
        plan_resp = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "lane_pruning_k": 3,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert plan_resp.status_code == 200
        plan_data = plan_resp.json()
        run_id = plan_data["run_id"]
        assert run_id.startswith("run_20240115_")

        # 2. Retrieve via GET /api/runs/{run_id}
        run_resp = api_client.get(f"/api/runs/{run_id}")
        assert run_resp.status_code == 200
        manifest = run_resp.json()

        assert manifest["run_id"] == run_id
        assert manifest["run_type"] == "PLAN"
        assert manifest["origin_date"] == "2024-01-15"
        assert manifest["status"] == "OK"
        assert manifest["dataset_hash"] is not None
        assert "optiqo" in manifest["software_versions"]
        assert manifest["solver_status"] in ("OPTIMAL", "TIME_LIMITED_FEASIBLE")
        assert manifest["checker_verdict"]["passed"] is True
        assert len(manifest["plan_lines"]) > 0

    def test_backtest_persistence_and_retrieval(self, clean_dataset_dir: Path, api_client: TestClient):
        """Test POST /api/backtest automatically persists backtest run manifest."""
        backtest_resp = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "policies": ["B1"],
            },
        )
        assert backtest_resp.status_code == 200
        b_data = backtest_resp.json()
        run_id = b_data["run_id"]
        assert run_id.startswith("backtest_")

        # Retrieve via GET /api/runs/{run_id}
        run_resp = api_client.get(f"/api/runs/{run_id}")
        assert run_resp.status_code == 200
        manifest = run_resp.json()
        assert manifest["run_id"] == run_id
        assert manifest["run_type"] == "BACKTEST"
        assert manifest["status"] == "COMPLETED"

    def test_list_runs(self, api_client: TestClient):
        """Test GET /api/runs returns list of stored run summaries."""
        resp = api_client.get("/api/runs")
        assert resp.status_code == 200
        runs_list = resp.json()
        assert isinstance(runs_list, list)

    def test_get_run_missing_returns_404(self, api_client: TestClient):
        """Test GET /api/runs/{run_id} returns 404 for unknown run."""
        resp = api_client.get("/api/runs/nonexistent_run_id_000")
        assert resp.status_code == 404
        assert resp.json().get("code") == "RUN_NOT_FOUND"

    def test_export_plan_csv_and_json(self, api_client: TestClient):
        """Test GET /api/runs/{run_id}/export for plan artifact."""
        # Save a dedicated test run with a formula string in explanation
        test_run_id = "run_export_test_plan_001"
        save_run({
            "run_id": test_run_id,
            "run_type": "PLAN",
            "origin_date": "2024-01-15",
            "dataset_hash": "hash123",
            "status": "OK",
            "summary": {"total_shipped_units": 100, "total_freight_cost": 50.0},
            "plan_lines": [
                {
                    "line_id": "L1",
                    "warehouse_id": "WH_01",
                    "batch_id": "B1",
                    "sku_id": "SKU_01",
                    "dest_id": "DEST_01",
                    "quantity": 100,
                    "arrival_date": "2024-01-17",
                    "total_freight_cost": 50.0,
                    "explanation": {"sentence": "=1+2 formula injection test"},
                }
            ],
        })

        # 1. Export CSV
        resp_csv = api_client.get(f"/api/runs/{test_run_id}/export?artifact=plan&format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert 'attachment; filename="run_export_test_plan_001_plan.csv"' in resp_csv.headers["content-disposition"]
        csv_text = resp_csv.text
        # Verify formula neutralization
        assert "'=1+2 formula injection test" in csv_text
        assert "WH_01" in csv_text

        # 2. Export JSON
        resp_json = api_client.get(f"/api/runs/{test_run_id}/export?artifact=plan&format=json")
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers["content-type"]
        data = resp_json.json()
        assert data["run_id"] == test_run_id
        assert len(data["plan_lines"]) == 1

    def test_export_risks_and_kpis(self, api_client: TestClient):
        """Test GET /api/runs/{run_id}/export for risks and kpis artifacts."""
        test_run_id = "run_export_test_metrics_002"
        save_run({
            "run_id": test_run_id,
            "run_type": "PLAN",
            "origin_date": "2024-01-15",
            "dataset_hash": "hash456",
            "status": "OK",
            "summary": {
                "expected_unmet_demand_before": 120.0,
                "expected_unmet_demand_after": 15.0,
            },
            "kpi_comparison": {
                "unmet_demand_rate_k1": {"b1": 0.05, "optiqo": 0.02},
            },
        })

        # Export risks CSV
        resp_r = api_client.get(f"/api/runs/{test_run_id}/export?artifact=risks&format=csv")
        assert resp_r.status_code == 200
        assert "expected_unmet_demand_before" in resp_r.text

        # Export kpis CSV
        resp_k = api_client.get(f"/api/runs/{test_run_id}/export?artifact=kpis&format=csv")
        assert resp_k.status_code == 200
        assert "unmet_demand_rate_k1" in resp_k.text

    def test_export_invalid_parameters_return_422(self, api_client: TestClient):
        """Test export with invalid format or artifact returns HTTP 422."""
        test_run_id = "run_export_test_003"
        save_run({"run_id": test_run_id, "dataset_hash": "dummy"})

        # Bad format
        resp_fmt = api_client.get(f"/api/runs/{test_run_id}/export?artifact=plan&format=parquet")
        assert resp_fmt.status_code == 422

        # Bad artifact
        resp_art = api_client.get(f"/api/runs/{test_run_id}/export?artifact=unsupported_art&format=csv")
        assert resp_art.status_code == 422

    def test_export_missing_run_returns_404(self, api_client: TestClient):
        """Test export for missing run returns HTTP 404."""
        resp = api_client.get("/api/runs/nonexistent_export_run/export?artifact=plan&format=csv")
        assert resp.status_code == 404
