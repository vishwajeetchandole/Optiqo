"""
Optiqo — Computational Engine Protocols (PRD §5.1, Plan §5)

Typed Python Protocol definitions isolating forecasting and optimization engines
from the FastAPI transport and orchestration layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

import pandas as pd


# ── 1. Demand Forecasting Protocol ────────────────────────────────────────────

@dataclass(frozen=True)
class ForecastRequestPayload:
    """Inputs passed into ForecasterProtocol.generate_forecast."""

    sales_daily: pd.DataFrame
    skus: pd.DataFrame
    calendar_events: pd.DataFrame
    destinations: pd.DataFrame
    origin_date: str
    horizon_days: int = 7
    validation_window_weeks: int = 12


@dataclass(frozen=True)
class ForecastRowResult:
    """One destination-SKU forecast result row."""

    sku_id: str
    dest_id: str
    selected_method: str              # "LIGHTGBM", "SEASONAL_NAIVE", "MA_28", "FALLBACK_PROFILE"
    is_fallback: bool
    daily_forecasts: list[float]      # Length == horizon_days
    horizon_mean: float               # Sum of daily_forecasts
    low_multiplier: float             # 10th percentile empirical ratio
    mid_multiplier: float             # 50th percentile empirical ratio
    high_multiplier: float            # 90th percentile empirical ratio
    low_horizon_demand: float
    mid_horizon_demand: float
    high_horizon_demand: float


@dataclass(frozen=True)
class ForecastEngineOutput:
    """Result returned by ForecasterProtocol."""

    status: str                       # "OK", "FALLBACK_FORECAST", "ERROR"
    forecast_table: pd.DataFrame      # DataFrame conforming to ForecastRowResult fields
    validation_wape_by_method: dict[str, float]
    coverage_rate: float              # F5 metric: fraction of actuals between low and high
    diagnostics: dict[str, Any]


@runtime_checkable
class ForecasterProtocol(Protocol):
    """Protocol for demand forecasting engines."""

    def generate_forecast(self, payload: ForecastRequestPayload) -> ForecastEngineOutput:
        """
        Execute chronological forecast with strict leakage protection.
        Fallbacks must trigger automatically on short history or model failure.
        """
        ...


# ── 2. Allocation Optimizer Protocol ──────────────────────────────────────────

@dataclass(frozen=True)
class OptimizerConfig:
    """Solver parameters and cost factors for allocation optimization."""

    shortage_penalty_factor: float = 1.5
    holding_cost_rate: float = 0.02
    lane_pruning_k: int = 3
    solver_timeout_seconds: int = 60
    allow_time_limited_suboptimal: bool = True


@dataclass(frozen=True)
class PlannedShipmentLine:
    """One allocated shipment line from warehouse batch to destination."""

    line_id: str
    warehouse_id: str
    batch_id: str
    sku_id: str
    dest_id: str
    quantity: int                     # Integer rounded down (C4)
    arrival_date: str
    remaining_life_at_arrival: int
    min_required_life: int
    unit_freight_cost: float
    total_freight_cost: float
    batch_fully_allocated: bool
    destination_capacity_binding: bool
    next_best_warehouse_id: Optional[str]
    next_best_freight_cost: Optional[float]


@dataclass(frozen=True)
class OptimizerEngineOutput:
    """Result returned by OptimizerProtocol."""

    status: str                       # "OPTIMAL", "SOLVER_TIMEOUT", "INFEASIBLE", "ERROR"
    objective_value: float
    solver_runtime_seconds: float
    lines: list[PlannedShipmentLine]
    rounding_loss_units: int
    unmet_demand_by_dest_sku: pd.DataFrame
    expected_expiry_by_dest_sku: pd.DataFrame
    slack_data: dict[str, Any]


@runtime_checkable
class OptimizerProtocol(Protocol):
    """Protocol for lot-by-lot allocation optimization engines."""

    def optimize_allocation(
        self,
        usable_inventory: pd.DataFrame,
        forecast_table: pd.DataFrame,
        destinations: pd.DataFrame,
        skus: pd.DataFrame,
        lanes: pd.DataFrame,
        config: OptimizerConfig,
        origin_date: Optional[str] = None,
    ) -> OptimizerEngineOutput:
        """
        Solve lot-by-lot continuous LP.
        Post-process with conservative integer round-down and report slacks.
        """
        ...


# ── 3. Independent Constraint Verification Protocol ───────────────────────────

@dataclass(frozen=True)
class ConstraintViolation:
    """Detailed record of an individual constraint violation found by independent checker."""

    constraint_id: str                # "C1_BATCH_STOCK", "C2_ELIGIBILITY", "C3_DEST_CAPACITY", "C4_NON_NEGATIVE_INT", "C5_LANE"
    entity_id: str                    # Batch ID, Destination ID, or (Destination, SKU)
    violation_message: str
    observed_value: float
    limit_value: float


@dataclass(frozen=True)
class VerificationResult:
    """Aggregated output from independent constraint checker."""

    passed: bool
    total_violations: int
    violations: list[ConstraintViolation]
    checked_rules_summary: dict[str, int]


@runtime_checkable
class ConstraintVerifierProtocol(Protocol):
    """Protocol for independent hard-constraint checkers."""

    def verify_plan(
        self,
        plan_lines: list[PlannedShipmentLine],
        initial_batches: pd.DataFrame,
        destinations: pd.DataFrame,
        skus: pd.DataFrame,
        lanes: pd.DataFrame,
        origin_date: str,
        inbound_shipments: Optional[pd.DataFrame] = None,
        destination_batches: Optional[pd.DataFrame] = None,
        lane_pruning_k: int = 3,
        warehouses: Optional[pd.DataFrame] = None,
    ) -> VerificationResult:
        """
        Independent verification of C1-C5 hard constraints on integer-rounded allocations.
        Must run outside the solver and report zero violations for plan acceptance.
        """
        ...

