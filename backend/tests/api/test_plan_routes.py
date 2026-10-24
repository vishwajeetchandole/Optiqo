"""
Optiqo — Plan API Route Integration & Regression Tests (PRD §5.1 P0-05, Plan §4.5)

Tests:
1. POST /api/plan success on clean dataset (HTTP 200, schema, checker status, explanations).
2. POST /api/plan error handling (404 for missing dataset, 422 for invalid date, 422 for validation faults).
3. POST /api/plan with custom cost parameters and lane pruning k.
4. Regression compatibility across all existing endpoints (/health, /demo-data, /data/validate, /risk, /forecast).
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import pandas as pd


class TestPlanAPI:
    def test_plan_success_on_clean_data(self, clean_dataset_dir: Path, api_client: TestClient):
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "lane_pruning_k": 3,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "OK"
        assert data["origin_date"] == "2024-01-15"
        assert data["solver_status"] in ("OPTIMAL", "TIME_LIMITED_FEASIBLE")
        assert data["checker_status"]["passed"] is True
        assert data["checker_status"]["violations_count"] == 0
        assert data["checker_status"]["violations"] == []

        # Summary
        summary = data["summary"]
        assert summary["total_shipped_units"] >= 0
        assert summary["total_freight_cost"] >= 0.0
        assert summary["expected_unmet_demand_before"] >= 0.0
        assert summary["expected_unmet_demand_after"] >= 0.0
        assert summary["supply_bound_unavoidable_shortage"] >= 0.0

        # Plan lines and explanations
        plan_lines = data["plan_lines"]
        assert len(plan_lines) > 0
        first_line = plan_lines[0]
        assert "line_id" in first_line
        assert "warehouse_id" in first_line
        assert "batch_id" in first_line
        assert "sku_id" in first_line
        assert "dest_id" in first_line
        assert "quantity" in first_line
        assert first_line["quantity"] > 0
        assert "explanation" in first_line
        assert "evidence" in first_line["explanation"]
        assert "sentence" in first_line["explanation"]
        assert len(first_line["explanation"]["sentence"]) > 0

    def test_plan_with_custom_cost_parameters(self, clean_dataset_dir: Path, api_client: TestClient):
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "cost_parameters": {
                    "shortage_penalty_factor": 2.5,
                    "holding_cost_rate": 0.05,
                },
                "lane_pruning_k": 2,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        assert data["checker_status"]["passed"] is True

    def test_plan_missing_dataset_returns_404(self, api_client: TestClient):
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "dataset_path": "nonexistent/directory/path/here",
            },
        )
        assert response.status_code == 404

    def test_plan_invalid_origin_date_returns_422(self, clean_dataset_dir: Path, api_client: TestClient):
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "not-a-valid-date",
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert response.status_code == 422

    def test_plan_blocking_validation_fault_returns_422(
        self, clean_dataset_dir: Path, tmp_path: Path, api_client: TestClient
    ):
        """Dataset with injected transit_days = 0 must return HTTP 422 VALIDATION_FAILED."""
        corrupt_dir = tmp_path / "corrupt_lanes"
        corrupt_dir.mkdir()
        for f in clean_dataset_dir.glob("*.csv"):
            corrupt_dir.joinpath(f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        # Corrupt transit_days
        lanes_file = corrupt_dir / "lanes.csv"
        lanes_df = pd.read_csv(lanes_file)
        lanes_df.loc[0, "transit_days"] = 0
        lanes_df.to_csv(lanes_file, index=False)

        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "dataset_path": str(corrupt_dir),
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert "validation" in str(data).lower() or "error" in str(data).lower()

    def test_regression_existing_api_endpoints(self, clean_dataset_dir: Path, api_client: TestClient):
        """Preserve contracts for /health, /demo-data, /data/validate, /risk, and /forecast."""
        # 1. GET /api/health
        health_resp = api_client.get("/api/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "HEALTHY"

        # 2. GET /api/demo-data
        demo_resp = api_client.get("/api/demo-data?seed=42")
        assert demo_resp.status_code == 200
        assert demo_resp.json()["parameters"]["seed"] == 42

        # 3. POST /api/data/validate
        val_resp = api_client.post(
            "/api/data/validate",
            json={"dataset_path": str(clean_dataset_dir), "planning_date": "2024-01-15"},
        )
        assert val_resp.status_code == 200
        assert val_resp.json()["status"] in ("VALID", "WARNINGS_ONLY")

        # 4. GET /api/risk
        risk_resp = api_client.get("/api/risk?origin_date=2024-01-15")
        assert risk_resp.status_code == 200
        assert "alerts" in risk_resp.json()

        # 5. POST /api/forecast
        fc_resp = api_client.post(
            "/api/forecast",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "dataset_path": str(clean_dataset_dir),
                "use_cache": True,
            },
        )
        assert fc_resp.status_code == 200
        assert "forecasts" in fc_resp.json()

    def test_plan_with_cost_params_and_dataset_dir_aliases(
        self, clean_dataset_dir: Path, api_client: TestClient
    ):
        """Reconciles Plan §295 field names: cost_params and dataset_dir aliases."""
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "cost_params": {
                    "shortage_penalty_factor": 1.8,
                    "holding_cost_rate": 0.03,
                },
                "dataset_dir": str(clean_dataset_dir),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        assert data["checker_status"]["passed"] is True

    def test_plan_defaults_when_optional_fields_omitted(
        self, clean_dataset_dir: Path, api_client: TestClient
    ):
        """Verify request succeeds with minimal payload (defaults for horizon, cost, timeout, pruning)."""
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"

    def test_plan_boundary_validation_horizon_and_timeout(
        self, clean_dataset_dir: Path, api_client: TestClient
    ):
        """Invalid horizon_days (<= 0 or > 28) and invalid timeout (<= 0) return 422."""
        # 1. horizon_days = 0
        resp1 = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 0,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert resp1.status_code == 422

        # 2. horizon_days = 35 (exceeds max 28)
        resp2 = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 35,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert resp2.status_code == 422

        # 3. solver_timeout_seconds = 0
        resp3 = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "solver_timeout_seconds": 0,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert resp3.status_code == 422
