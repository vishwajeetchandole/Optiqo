"""
Optiqo — Multi-Cycle Simulation & Backtest API Route Integration Tests (PRD §5.1 P0-09, Plan §4.7)

Tests:
1. POST /api/backtest success on clean dataset (HTTP 200, schema, KPIComparison, ForecastKPIs, OptimizationKPIs).
2. POST /api/backtest alias dataset_dir and dataset_path support.
3. POST /api/backtest error handling:
   - 404 for non-existent dataset directory.
   - 422 for invalid date format.
   - 422 for corrupted dataset failing 13-fault validation.
4. Regression compatibility across all existing endpoints (/health, /demo-data, /data/validate, /risk, /forecast, /plan).
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import pandas as pd


class TestBacktestAPI:
    def test_backtest_success_on_clean_data(self, clean_dataset_dir: Path, api_client: TestClient):
        """Test POST /api/backtest executes multi-cycle simulation and returns comprehensive KPIs."""
        response = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "policies": ["B1", "B2", "OPTIQO"],
                "baseline_safety_days": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "COMPLETED"
        assert "run_id" in data
        assert data["window_days"] == 14
        assert data["dispatch_cycles"] == 2

        # KPI Comparison
        kpi = data["kpi_comparison"]
        assert "unmet_demand_rate_k1" in kpi
        assert "fill_rate_k2" in kpi
        assert "stockout_days_rate_k3" in kpi
        assert "expiry_wastage_units_k4" in kpi
        assert "total_freight_cost_k5" in kpi
        assert "total_modeled_cost_k6" in kpi
        assert "ending_inventory_units_k7" in kpi
        assert "gain_decomposition_k8" in kpi

        # Check gain decomposition invariants
        decomp = kpi["gain_decomposition_k8"]
        assert "unmet_demand_rate" in decomp
        assert "total_modeled_cost" in decomp

        # Forecast KPIs
        fc = data["forecast_kpis"]
        assert "daily_wape_f1" in fc
        assert "weekly_wape_f2" in fc
        assert "bias_f4" in fc
        assert "interval_coverage_f5" in fc

        # Optimization KPIs
        opt = data["optimization_kpis"]
        assert opt["constraint_violations_o1"] == 0
        assert opt["feasible_plan_rate_o2"] == 1.0
        assert opt["grounded_explanations_rate_o3"] == 1.0

    def test_backtest_dataset_dir_alias(self, clean_dataset_dir: Path, api_client: TestClient):
        """Test POST /api/backtest accepts 'dataset_dir' alias as alternative to 'dataset_path'."""
        response = api_client.post(
            "/api/backtest",
            json={
                "dataset_dir": str(clean_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "policies": ["B1"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"

    def test_backtest_missing_dataset_404(self, api_client: TestClient):
        """Test POST /api/backtest returns 404 when dataset directory does not exist."""
        response = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": "non_existent_folder_xyz_12345",
                "window_days": 14,
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert data.get("code") == "DATASET_NOT_FOUND" or "not found" in str(data).lower()

    def test_backtest_invalid_date_format_422(self, clean_dataset_dir: Path, api_client: TestClient):
        """Test POST /api/backtest returns 422 for malformed evaluation_start_date."""
        response = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir),
                "evaluation_start_date": "invalid-date-format",
            },
        )
        assert response.status_code == 422

    def test_backtest_corrupted_dataset_validation_failure(
        self, corrupted_dataset_dir: Path, api_client: TestClient
    ):
        """Test POST /api/backtest runs 13-fault validator and rejects corrupted dataset with 422."""
        # Inject negative inventory quantity to trigger blocking fault
        inv_path = corrupted_dataset_dir / "inventory_batches.csv"
        df = pd.read_csv(inv_path)
        df.loc[0, "quantity"] = -999.0
        df.to_csv(inv_path, index=False)

        response = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(corrupted_dataset_dir),
                "window_days": 14,
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert data.get("code") == "VALIDATION_FAILED" or "validation" in str(data).lower()

    def test_regression_existing_endpoints(self, clean_dataset_dir: Path, api_client: TestClient):
        """Verify adding backtest route did not break existing Phase 1-5 endpoints."""
        # Health
        resp_health = api_client.get("/api/health")
        assert resp_health.status_code == 200

        # Validate
        resp_val = api_client.post("/api/data/validate", json={"dataset_path": str(clean_dataset_dir)})
        assert resp_val.status_code == 200

        # Risk
        resp_risk = api_client.get(
            f"/api/risk?origin_date=2024-01-15&dataset_path={clean_dataset_dir}"
        )
        assert resp_risk.status_code == 200

        # Forecast
        resp_fc = api_client.post(
            "/api/forecast",
            json={"dataset_path": str(clean_dataset_dir), "origin_date": "2024-01-15", "horizon_days": 7},
        )
        assert resp_fc.status_code == 200

        # Plan
        resp_plan = api_client.post(
            "/api/plan",
            json={"dataset_path": str(clean_dataset_dir), "origin_date": "2024-01-15", "horizon_days": 7},
        )
        assert resp_plan.status_code == 200
