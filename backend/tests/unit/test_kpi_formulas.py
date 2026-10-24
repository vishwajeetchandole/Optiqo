"""
Optiqo — Simulation KPI Formulas & Gain Decomposition Unit Tests (PRD §7, §10.7)
"""

from __future__ import annotations

import pytest
from backend.simulation.kpi import compute_all_kpis


class TestSimulationKPIFormulas:
    def test_k1_to_k7_and_gain_decomposition(self):
        """Test K1–K7 calculation and K8 gain decomposition mathematics."""
        policy_runs = {
            "B1": {
                "unmet_demand_rate": 0.068,
                "stockout_day_rate": 0.082,
                "expiry_units": 2400.0,
                "total_freight_cost": 182400.0,
                "total_shipped_units": 145920.0,
                "total_modeled_cost": 420500.0,
                "ending_inventory_units": 45200.0,
            },
            "B2": {
                "unmet_demand_rate": 0.051,
                "stockout_day_rate": 0.063,
                "expiry_units": 2100.0,
                "total_freight_cost": 179200.0,
                "total_shipped_units": 148000.0,
                "total_modeled_cost": 375200.0,
                "ending_inventory_units": 44800.0,
            },
            "OPTIQO": {
                "unmet_demand_rate": 0.032,
                "stockout_day_rate": 0.041,
                "expiry_units": 1250.0,
                "total_freight_cost": 168500.0,
                "total_shipped_units": 151800.0,
                "total_modeled_cost": 312400.0,
                "ending_inventory_units": 46100.0,
            },
        }

        fc_records = [
            {"cycle_id": 0, "dest_id": "D1", "sku_id": "S1", "predicted": 100.0, "actual": 90.0, "low": 80.0, "high": 120.0},
            {"cycle_id": 0, "dest_id": "D2", "sku_id": "S1", "predicted": 50.0, "actual": 55.0, "low": 40.0, "high": 65.0},
        ]
        opt_records = [
            {"runtime_seconds": 3.5, "status": "OK", "violations_count": 0, "supply_bound_shortage": 50.0},
            {"runtime_seconds": 4.2, "status": "OK", "violations_count": 0, "supply_bound_shortage": 60.0},
        ]

        kpi_comp, fc_kpis, opt_kpis = compute_all_kpis(
            policy_runs=policy_runs,
            forecast_eval_records=fc_records,
            optimization_eval_records=opt_records,
        )

        # 1. K1: Unmet Demand Rate
        assert kpi_comp.unmet_demand_rate_k1.b1 == 0.068
        assert kpi_comp.unmet_demand_rate_k1.b2 == 0.051
        assert kpi_comp.unmet_demand_rate_k1.optiqo == 0.032
        # Relative reduction vs B1: (0.068 - 0.032) / 0.068 = 52.9%
        assert pytest.approx(kpi_comp.unmet_demand_rate_k1.relative_reduction_vs_b1_pct, 0.2) == 52.9
        assert kpi_comp.unmet_demand_rate_k1.target_met_vs_b1 is True

        # 2. K2: Fill Rate (1 - K1)
        assert pytest.approx(kpi_comp.fill_rate_k2.b1, 0.001) == 0.932
        assert pytest.approx(kpi_comp.fill_rate_k2.optiqo, 0.001) == 0.968
        assert kpi_comp.fill_rate_k2.target_met is True

        # 3. K3: Stockout Days Rate
        assert pytest.approx(kpi_comp.stockout_days_rate_k3.relative_reduction_vs_b1_pct, 0.2) == 50.0

        # 4. K4: Expiry Wastage Units
        assert pytest.approx(kpi_comp.expiry_wastage_units_k4.relative_reduction_vs_b1_pct, 0.2) == 47.9

        # 5. K5: Freight Cost Per Unit
        # B1: 182400 / 145920 = 1.25
        # Optiqo: 168500 / 151800 = 1.11
        assert kpi_comp.total_freight_cost_k5.per_unit_b1 == 1.25
        assert kpi_comp.total_freight_cost_k5.per_unit_optiqo == 1.11
        assert pytest.approx(kpi_comp.total_freight_cost_k5.relative_reduction_per_unit_pct, 0.2) == 11.2

        # 6. K6: Total Modeled Cost
        assert pytest.approx(kpi_comp.total_modeled_cost_k6.relative_reduction_vs_b1_pct, 0.2) == 25.7

        # 7. K7: Ending Inventory
        assert pytest.approx(kpi_comp.ending_inventory_units_k7.percentage_above_b1, 0.2) == 2.0

        # 8. K8: Gain Decomposition
        decomp = kpi_comp.gain_decomposition_k8
        # Unmet demand rate:
        # Forecast effect (B1 -> B2): 0.051 - 0.068 = -0.017
        # Allocation effect (B2 -> Optiqo): 0.032 - 0.051 = -0.019
        assert pytest.approx(decomp.unmet_demand_rate.forecast_effect_b1_to_b2, 0.001) == -0.017
        assert pytest.approx(decomp.unmet_demand_rate.allocation_effect_b2_to_optiqo, 0.001) == -0.019
        # Sum of effects matches total delta: -0.017 + (-0.019) = -0.036 = 0.032 - 0.068
        assert pytest.approx(
            decomp.unmet_demand_rate.forecast_effect_b1_to_b2 + decomp.unmet_demand_rate.allocation_effect_b2_to_optiqo,
            0.001,
        ) == (0.032 - 0.068)

        # Total modeled cost:
        # Forecast effect (B1 -> B2): 375200 - 420500 = -45300
        # Allocation effect (B2 -> Optiqo): 312400 - 375200 = -62800
        assert decomp.total_modeled_cost.forecast_effect_b1_to_b2 == -45300.0
        assert decomp.total_modeled_cost.allocation_effect_b2_to_optiqo == -62800.0

        # 9. Forecast Quality F1–F5
        assert fc_kpis.daily_wape_f1 >= 0.0
        assert fc_kpis.interval_coverage_f5 == 1.0  # Both actuals in interval

        # 10. Optimization Quality O1–O5
        assert opt_kpis.constraint_violations_o1 == 0
        assert opt_kpis.feasible_plan_rate_o2 == 1.0
        assert opt_kpis.p95_solver_runtime_seconds_o4 >= 3.5
