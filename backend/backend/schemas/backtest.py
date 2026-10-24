"""
Optiqo — Multi-Cycle Simulation & Backtest Request/Response Schemas (PRD §7, §10.8, Plan §4.7)
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class BacktestRequest(BaseModel):
    """Payload for POST /api/backtest."""

    dataset_path: Optional[str] = Field(
        default=None,
        description="Path to dataset directory. Uses demo data if omitted",
    )
    seed: Optional[int] = Field(
        default=42,
        description="Synthetic dataset seed if demo data is used",
    )
    window_days: int = Field(
        default=56,
        ge=7,
        le=112,
        description="Evaluation window length in days (default 56 days / 8 weekly cycles)",
    )
    evaluation_start_date: Optional[str] = Field(
        default=None,
        description="Start date of evaluation window (YYYY-MM-DD). Defaults to dataset evaluation start if omitted",
    )
    baseline_safety_days: int = Field(
        default=2,
        ge=0,
        le=14,
        description="Safety days buffer for baseline policies B1 and B2 (default 2 days)",
    )
    policies: list[str] = Field(
        default_factory=lambda: ["B1", "B2", "OPTIQO"],
        description="List of policies to simulate (e.g. ['B1', 'B2', 'OPTIQO'])",
    )

    @model_validator(mode="before")
    @classmethod
    def _reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "dataset_dir" in data and "dataset_path" not in data:
                data["dataset_path"] = data["dataset_dir"]
        return data


class KPIComparisonK1(BaseModel):
    b1: float
    b2: float
    optiqo: float
    target_met_vs_b1: bool
    relative_reduction_vs_b1_pct: float
    relative_reduction_vs_b2_pct: float


class KPIComparisonK2(BaseModel):
    b1: float
    b2: float
    optiqo: float
    target_met: bool


class KPIComparisonK3(BaseModel):
    b1: float
    b2: float
    optiqo: float
    relative_reduction_vs_b1_pct: float


class KPIComparisonK4(BaseModel):
    b1: float
    b2: float
    optiqo: float
    relative_reduction_vs_b1_pct: float


class KPIComparisonK5(BaseModel):
    b1: float
    b2: float
    optiqo: float
    per_unit_b1: float
    per_unit_optiqo: float
    relative_reduction_per_unit_pct: float


class KPIComparisonK6(BaseModel):
    b1: float
    b2: float
    optiqo: float
    relative_reduction_vs_b1_pct: float


class KPIComparisonK7(BaseModel):
    b1: float
    b2: float
    optiqo: float
    percentage_above_b1: float


class GainDecompositionItem(BaseModel):
    forecast_effect_b1_to_b2: float
    allocation_effect_b2_to_optiqo: float


class GainDecompositionK8(BaseModel):
    unmet_demand_rate: GainDecompositionItem
    total_modeled_cost: GainDecompositionItem


class KPIComparison(BaseModel):
    unmet_demand_rate_k1: KPIComparisonK1
    fill_rate_k2: KPIComparisonK2
    stockout_days_rate_k3: KPIComparisonK3
    expiry_wastage_units_k4: KPIComparisonK4
    total_freight_cost_k5: KPIComparisonK5
    total_modeled_cost_k6: KPIComparisonK6
    ending_inventory_units_k7: KPIComparisonK7
    gain_decomposition_k8: GainDecompositionK8


class ForecastKPIs(BaseModel):
    daily_wape_f1: float
    weekly_wape_f2: float
    bias_f4: float
    interval_coverage_f5: float


class OptimizationKPIs(BaseModel):
    constraint_violations_o1: int
    feasible_plan_rate_o2: float
    grounded_explanations_rate_o3: float
    p95_solver_runtime_seconds_o4: float
    supply_bound_shortage_o5: float


class BacktestResponse(BaseModel):
    status: str
    run_id: str
    window_days: int
    dispatch_cycles: int
    seed: int
    kpi_comparison: KPIComparison
    forecast_kpis: ForecastKPIs
    optimization_kpis: OptimizationKPIs
