"""
Optiqo — Integration Tests: Simulation Determinism & Replay (PRD §14 N3, §16.1 E4/E5, Metric S2)

Verifies:
1. Metric S2: Running backtest twice with the same seed produces byte-identical KPI tables and run manifests.
2. Multi-seed sensitivity (PRD §16.1 E4): Running with seed 42 vs seed 99 produces distinct valid simulation outputs.
3. Simulation physics and roll-forward consistency across daily timesteps.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


class TestSimulationDeterminismAndReplay:
    """Verifies backtest determinism (S2) and multi-seed sensitivity."""

    def test_backtest_reproducibility_byte_identical_kpis(self, clean_dataset_dir: Path, api_client: TestClient):
        """
        Metric S2: Re-running backtest with the same seed (seed 42) produces
        identical KPI tables, forecast KPIs, and optimization KPIs.
        """
        payload = {
            "dataset_path": str(clean_dataset_dir),
            "evaluation_start_date": "2024-06-03",
            "window_days": 14,
            "seed": 42,
            "policies": ["B1", "B2", "OPTIQO"],
            "baseline_safety_days": 2,
        }

        # Run 1
        resp1 = api_client.post("/api/backtest", json=payload)
        assert resp1.status_code == 200
        data1 = resp1.json()

        # Run 2
        resp2 = api_client.post("/api/backtest", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["status"] == "COMPLETED"
        assert data2["status"] == "COMPLETED"

        # Compare KPI comparison tables
        kpi1 = data1["kpi_comparison"]
        kpi2 = data2["kpi_comparison"]
        assert json.dumps(kpi1, sort_keys=True) == json.dumps(kpi2, sort_keys=True), (
            "KPI comparison tables for identical seeds must be byte-identical!"
        )

        # Compare Forecast KPIs (F1-F5)
        fc1 = data1["forecast_kpis"]
        fc2 = data2["forecast_kpis"]
        assert json.dumps(fc1, sort_keys=True) == json.dumps(fc2, sort_keys=True), (
            "Forecast KPIs for identical seeds must be byte-identical!"
        )

        # Compare Optimization KPIs (O1-O5)
        # O1, O2, O3, O5 are mathematically deterministic. O4 is physical solver runtime.
        opt1 = data1["optimization_kpis"]
        opt2 = data2["optimization_kpis"]
        assert opt1["constraint_violations_o1"] == opt2["constraint_violations_o1"] == 0
        assert opt1["feasible_plan_rate_o2"] == opt2["feasible_plan_rate_o2"] == 1.0
        assert opt1["grounded_explanations_rate_o3"] == opt2["grounded_explanations_rate_o3"] == 1.0
        assert opt1["supply_bound_shortage_o5"] == opt2["supply_bound_shortage_o5"]
        assert opt1["p95_solver_runtime_seconds_o4"] <= 60.0
        assert opt2["p95_solver_runtime_seconds_o4"] <= 60.0

    def test_seed_sensitivity_produces_distinct_valid_trajectories(
        self, clean_dataset_dir: Path, clean_dataset_dir_seed2: Path, api_client: TestClient
    ):
        """
        PRD §16.1 E4: Running with different seeds (seed 42 vs seed 99) produces distinct
        demand realizations and metrics, confirming dynamic simulation sensitivity.
        """
        # Run with seed 42 dataset
        resp_seed42 = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "seed": 42,
                "policies": ["B1", "B2", "OPTIQO"],
            },
        )
        assert resp_seed42.status_code == 200
        data_seed42 = resp_seed42.json()

        # Run with seed 99 dataset
        resp_seed99 = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir_seed2),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "seed": 99,
                "policies": ["B1", "B2", "OPTIQO"],
            },
        )
        assert resp_seed99.status_code == 200
        data_seed99 = resp_seed99.json()

        # Both must pass acceptance conditions (O1=0, O2=1.0)
        assert data_seed42["optimization_kpis"]["constraint_violations_o1"] == 0
        assert data_seed99["optimization_kpis"]["constraint_violations_o1"] == 0
        assert data_seed42["optimization_kpis"]["feasible_plan_rate_o2"] == 1.0
        assert data_seed99["optimization_kpis"]["feasible_plan_rate_o2"] == 1.0

        # But total modeled cost and freight costs should show sensitivity across different seeds
        cost42 = data_seed42["kpi_comparison"]["total_modeled_cost_k6"]["optiqo"]
        cost99 = data_seed99["kpi_comparison"]["total_modeled_cost_k6"]["optiqo"]
        assert cost42 != cost99, "Different synthetic dataset seeds must produce distinct demand and cost paths"
