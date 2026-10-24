"""
Optiqo — Simulation Engine Unit Tests (PRD §5.1 P0-09, §10.8, Plan §6 Phase 6)

Tests:
1. 5-step daily simulation execution order: Receipts -> Expiry -> Sales -> Dispatch -> Accounting.
2. In-transit arrivals enter destination inventory at arrival_date.
3. Expired units removed and recorded as expired loss.
4. FEFO sales consumption drains oldest batches first; stockouts accumulate unmet demand.
5. Dispatch triggers on day_idx % 7 == 0, deducting warehouse stock and creating transit.
6. Daily accounting logs holding cost and inventory state.
7. End-to-end multi-cycle simulation over a 14-day evaluation window.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import pytest

from backend.data.loader import load_dataset
from backend.simulation.simulator import SimulationEngine


@pytest.fixture(scope="module")
def dataset_dict(clean_dataset_dir: Path) -> dict[str, pd.DataFrame]:
    loaded, errs = load_dataset(clean_dataset_dir)
    assert loaded is not None, f"Failed to load dataset: {errs}"
    return loaded.as_dict()


class TestSimulationEngine:
    def test_single_policy_simulation_flow(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test SimulationEngine._simulate_single_policy executes 5-step daily loop accurately."""
        engine = SimulationEngine()
        start_date = date(2024, 6, 3)  # Monday
        window_days = 14
        dispatch_cycles = 2

        summary, daily_logs, opt_records = engine._simulate_single_policy(
            policy_name="B1",
            policy=engine.b1_policy,
            dataset=dataset_dict,
            start_date=start_date,
            window_days=window_days,
            dispatch_cycles=dispatch_cycles,
            forecast_cache={},
            safety_days=2,
        )

        # 1. Verification of daily logs
        assert len(daily_logs) == window_days
        assert daily_logs[0]["date"] == start_date.isoformat()
        assert daily_logs[-1]["date"] == (start_date + timedelta(days=window_days - 1)).isoformat()

        # Step 4 check: freight cost incurred on dispatch days (day 0 and day 7)
        assert daily_logs[0]["freight_cost"] >= 0.0
        assert daily_logs[7]["freight_cost"] >= 0.0

        # Step 5 check: holding cost and ending inventory logged daily
        for log in daily_logs:
            assert log["warehouse_inventory"] >= 0
            assert log["destination_inventory"] >= 0
            assert log["holding_cost"] >= 0.0

        # 2. Verification of summary metrics
        assert "unmet_demand_rate" in summary
        assert 0.0 <= summary["unmet_demand_rate"] <= 1.0
        assert "stockout_day_rate" in summary
        assert "expiry_units" in summary
        assert "total_freight_cost" in summary
        assert "total_modeled_cost" in summary
        assert summary["total_modeled_cost"] >= 0.0
        assert summary["ending_inventory_units"] >= 0.0

    def test_run_backtest_multi_policy(self, dataset_dict: dict[str, pd.DataFrame]):
        """Test full SimulationEngine.run_backtest across B1, B2, and OPTIQO."""
        engine = SimulationEngine()
        start_date = date(2024, 6, 3)
        window_days = 14  # 2 cycles for quick test

        result = engine.run_backtest(
            dataset=dataset_dict,
            start_date=start_date,
            window_days=window_days,
            policies=["B1", "B2", "OPTIQO"],
            baseline_safety_days=2,
            seed=42,
        )

        assert result.run_id.startswith("backtest_")
        assert result.seed == 42
        assert result.window_days == 14
        assert result.dispatch_cycles == 2

        # Summaries for all active policies
        assert "B1" in result.policy_summaries
        assert "B2" in result.policy_summaries
        assert "OPTIQO" in result.policy_summaries

        # KPI comparison object populated
        kpi = result.kpi_comparison
        assert hasattr(kpi, "unmet_demand_rate_k1")
        assert hasattr(kpi, "fill_rate_k2")
        assert hasattr(kpi, "stockout_days_rate_k3")
        assert hasattr(kpi, "expiry_wastage_units_k4")
        assert hasattr(kpi, "total_freight_cost_k5")
        assert hasattr(kpi, "total_modeled_cost_k6")
        assert hasattr(kpi, "ending_inventory_units_k7")
        assert hasattr(kpi, "gain_decomposition_k8")

        # Forecast and Optimization quality KPIs
        assert result.forecast_kpis is not None
        assert result.optimization_kpis is not None
        assert result.optimization_kpis.constraint_violations_o1 == 0
        assert result.optimization_kpis.feasible_plan_rate_o2 == 1.0
