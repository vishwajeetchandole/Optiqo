"""
Optiqo — Integration Tests: End-to-End Planning Pipeline Acceptance (PRD §5.1, §7, §16.1 E2/E3, Checkpoints C, D, E)

Verifies:
1. Single-cycle planning pipeline acceptance:
   - Zero hard constraint violations (O1 = 0).
   - 100% feasible plan rate (O2 = 1.0).
   - 100% grounded explanations rate (O3 = 1.0) with complete evidence.
   - Solver runtime under 60 seconds (O4, PRD N2).
   - Supply-bound unavoidable shortage (O5) and allocation-caused shortage.
2. Multi-cycle simulation acceptance:
   - Full rolling replay across B1, B2, and Optiqo policies.
   - Zero violations (O1 = 0), 100% feasibility (O2 = 1.0), 100% grounded explanations (O3 = 1.0).
   - K8 Gain Decomposition invariant:
     Forecast Effect (B1->B2) + Allocation Effect (B2->Optiqo) == Total Modeled Cost Delta (B1->Optiqo).
   - Business KPI superiority: Optiqo reduces unmet demand rate (K1) and total modeled cost (K6) vs B1.
"""

from __future__ import annotations

import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


class TestPlanningPipelineAcceptance:
    """Verifies end-to-end planning and simulation acceptance targets."""

    def test_single_cycle_planning_pipeline_acceptance(self, clean_dataset_dir: Path, api_client: TestClient):
        """
        Tests single planning cycle satisfies:
        - O1 = 0 (zero violations)
        - O2 = 1.0 (feasible)
        - O3 = 1.0 (100% grounded explanations)
        - O4 <= 60s solver runtime
        - O5 supply-bound shortage calculation
        """
        t0 = time.perf_counter()
        response = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "lane_pruning_k": 3,
                "dataset_path": str(clean_dataset_dir),
                "cost_parameters": {
                    "shortage_penalty_factor": 1.5,
                    "holding_cost_rate": 0.02,
                },
            },
        )
        elapsed_total = time.perf_counter() - t0

        assert response.status_code == 200
        plan = response.json()

        # Status & Run ID
        assert plan["status"] == "OK"
        assert plan["solver_status"] in ("OPTIMAL", "TIME_LIMITED_FEASIBLE")
        assert plan["run_id"].startswith("run_20240115_")

        # Metric O1: Zero hard constraint violations
        checker = plan["checker_status"]
        assert checker["passed"] is True
        assert checker["violations_count"] == 0
        assert checker["violations"] == []

        # Metric O4: Solver runtime <= 60s, end-to-end <= 60s
        assert plan["solver_runtime_seconds"] <= 60.0
        assert elapsed_total <= 60.0

        # Summary & Metric O5: Supply-bound shortage
        summary = plan["summary"]
        assert summary["total_shipped_units"] >= 0
        assert summary["total_freight_cost"] > 0.0
        assert summary["supply_bound_unavoidable_shortage"] >= 0.0
        assert summary["allocation_caused_shortage"] >= 0.0

        # Optimization reduces unmet demand and expiry
        assert summary["expected_unmet_demand_after"] <= summary["expected_unmet_demand_before"]
        assert summary["expected_expiry_loss_after"] <= summary["expected_expiry_loss_before"]

        # Metric O3: 100% Grounded Explanations
        plan_lines = plan["plan_lines"]
        assert len(plan_lines) > 0
        assert summary["total_freight_cost"] == pytest.approx(
            sum(line["freight_cost"] for line in plan_lines)
        )

        for line in plan_lines:
            assert line["quantity"] > 0
            assert line["arrival_date"] >= "2024-01-15"
            rem_life = line.get("remaining_life_at_arrival_days") if "remaining_life_at_arrival_days" in line else line.get("remaining_life_at_arrival")
            min_life = line.get("min_required_life_days") if "min_required_life_days" in line else line.get("min_required_life")
            assert rem_life is not None and min_life is not None
            assert rem_life >= min_life

            # Explanation structure
            expl = line["explanation"]
            assert expl is not None
            assert len(expl["sentence"]) > 10
            ev = expl["evidence"]
            assert ev["shipped_quantity"] == line["quantity"]
            assert ev["remaining_shelf_life_arrival"] == rem_life
            assert ev["min_life_requirement"] == min_life
            freight = line.get("freight_cost") if "freight_cost" in line else line.get("unit_freight_cost")
            assert ev["freight_cost_selected"] == freight

    def test_multi_cycle_simulation_acceptance_and_gain_decomposition(
        self, clean_dataset_dir: Path, api_client: TestClient
    ):
        """
        Tests multi-cycle simulation replay satisfies:
        - O1 = 0, O2 = 1.0, O3 = 1.0 across all cycles.
        - Runtime <= 120s (Metric S1).
        - Gain decomposition invariant: Forecast Effect + Allocation Effect == Total Effect.
        - Business KPI directionality (K1, K2, K6).
        """
        t0 = time.perf_counter()
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
        elapsed_total = time.perf_counter() - t0

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "COMPLETED"
        assert data["dispatch_cycles"] == 2
        assert elapsed_total <= 120.0, f"Multi-cycle backtest took {elapsed_total:.2f}s > 120s"

        # Optimization KPIs
        opt_kpis = data["optimization_kpis"]
        assert opt_kpis["constraint_violations_o1"] == 0
        assert opt_kpis["feasible_plan_rate_o2"] == 1.0
        assert opt_kpis["grounded_explanations_rate_o3"] == 1.0
        assert opt_kpis["supply_bound_shortage_o5"] >= 0.0

        # Forecast KPIs
        fc_kpis = data["forecast_kpis"]
        assert fc_kpis["daily_wape_f1"] >= 0.0
        assert fc_kpis["weekly_wape_f2"] >= 0.0
        assert 0.0 <= fc_kpis["interval_coverage_f5"] <= 1.0

        # KPI Comparison
        kpi = data["kpi_comparison"]

        # K1 Unmet demand rate: Optiqo <= B1
        k1 = kpi["unmet_demand_rate_k1"]
        assert k1["optiqo"] <= k1["b1"], f"Optiqo K1 ({k1['optiqo']}) should be <= B1 ({k1['b1']})"

        # K2 Fill rate: Optiqo >= B1
        k2 = kpi["fill_rate_k2"]
        assert k2["optiqo"] >= k2["b1"], f"Optiqo K2 ({k2['optiqo']}) should be >= B1 ({k2['b1']})"

        # K6 Total modeled cost: Optiqo <= B1
        k6 = kpi["total_modeled_cost_k6"]
        assert k6["optiqo"] <= k6["b1"], f"Optiqo K6 ({k6['optiqo']}) should be <= B1 ({k6['b1']})"

        # K8 Gain Decomposition Invariants
        gain = kpi["gain_decomposition_k8"]

        # 1. Total Modeled Cost: Forecast Effect + Allocation Effect == Total Delta (Optiqo - B1)
        cost_gain = gain["total_modeled_cost"]
        fc_effect_cost = cost_gain["forecast_effect_b1_to_b2"]
        alloc_effect_cost = cost_gain["allocation_effect_b2_to_optiqo"]
        total_delta_cost = k6["optiqo"] - k6["b1"]

        assert pytest.approx(fc_effect_cost + alloc_effect_cost, abs=1.0) == total_delta_cost, (
            f"Gain decomposition invariant failed for cost: {fc_effect_cost} + {alloc_effect_cost} != {total_delta_cost}"
        )

        # 2. Unmet Demand Rate: Forecast Effect + Allocation Effect == Total Delta (Optiqo - B1)
        unmet_gain = gain["unmet_demand_rate"]
        fc_effect_unmet = unmet_gain["forecast_effect_b1_to_b2"]
        alloc_effect_unmet = unmet_gain["allocation_effect_b2_to_optiqo"]
        total_delta_unmet = k1["optiqo"] - k1["b1"]

        assert pytest.approx(fc_effect_unmet + alloc_effect_unmet, abs=0.001) == total_delta_unmet, (
            f"Gain decomposition invariant failed for unmet rate: {fc_effect_unmet} + {alloc_effect_unmet} != {total_delta_unmet}"
        )
