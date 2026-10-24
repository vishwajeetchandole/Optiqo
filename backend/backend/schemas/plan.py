"""
Optiqo — Plan Request & Response Schemas (PRD §5.1 P0-05, §10.5, Plan §4.5)
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class CostParameters(BaseModel):
    """Cost factors and multipliers for linear program objective function."""

    shortage_penalty_factor: float = Field(
        default=1.5,
        ge=0.0,
        description="Multiplier on unit margin for unmet demand penalty",
    )
    holding_cost_rate: float = Field(
        default=0.02,
        ge=0.0,
        description="Fraction of unit cost charged per unit in ending stock",
    )


class PlanRequest(BaseModel):
    """Payload for POST /api/plan."""

    origin_date: str = Field(
        description="Planning origin date (YYYY-MM-DD)",
        examples=["2026-10-24"],
    )
    horizon_days: int = Field(
        default=7,
        ge=1,
        le=28,
        description="Planning horizon in days",
    )
    cost_parameters: Optional[CostParameters] = Field(
        default=None,
        description="Cost parameters; defaults to PRD standard values if omitted",
    )
    solver_timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Maximum solver wall-clock time in seconds",
    )
    lane_pruning_k: int = Field(
        default=3,
        ge=1,
        description="Maximum warehouses considered per (dest, SKU) (C5)",
    )
    dataset_path: Optional[str] = Field(
        default=None,
        description="Optional path to dataset directory. Uses demo data if omitted",
    )

    @model_validator(mode="before")
    @classmethod
    def _reconcile_contract_aliases(cls, data: Any) -> Any:
        """Allow cost_params / dataset_dir aliases and unpack nested config if provided."""
        if isinstance(data, dict):
            # Alias: cost_params -> cost_parameters
            if "cost_params" in data and "cost_parameters" not in data:
                data["cost_parameters"] = data["cost_params"]
            # Alias: dataset_dir -> dataset_path
            if "dataset_dir" in data and "dataset_path" not in data:
                data["dataset_path"] = data["dataset_dir"]
            # Unpack nested config if caller structured as {"config": {...}}
            if "config" in data and isinstance(data["config"], dict):
                cfg = data["config"]
                for k in ("solver_timeout_seconds", "lane_pruning_k", "horizon_days"):
                    if k in cfg and k not in data:
                        data[k] = cfg[k]
        return data

    @property
    def cost_params(self) -> Optional[CostParameters]:
        """Convenience property matching Plan §295 terminology."""
        return self.cost_parameters

    @property
    def dataset_dir(self) -> Optional[str]:
        """Convenience property matching dataset_dir terminology."""
        return self.dataset_path


class ConstraintViolationItem(BaseModel):
    """Individual constraint violation details from independent verifier."""

    constraint_id: str
    entity_id: str
    violation_message: str
    observed_value: float
    limit_value: float


class CheckerStatus(BaseModel):
    """Status returned by independent constraint verifier."""

    passed: bool
    violations_count: int
    violations: list[ConstraintViolationItem] = Field(default_factory=list)


class PlanSummary(BaseModel):
    """High-level summary KPIs for the planning cycle."""

    total_shipped_units: int
    total_freight_cost: float
    expected_unmet_demand_before: float
    expected_unmet_demand_after: float
    expected_expiry_loss_before: float
    expected_expiry_loss_after: float
    supply_bound_unavoidable_shortage: float
    allocation_caused_shortage: float


class PlanLineEvidence(BaseModel):
    """Grounded evidence dictionary for an allocated shipment line."""

    forecast_mean: float
    forecast_range: list[float]
    current_stock: float
    inbound_stock: float
    shipped_quantity: int
    remaining_shelf_life_arrival: int
    min_life_requirement: int
    freight_cost_selected: float
    freight_cost_next_best: Optional[float] = None
    next_best_warehouse: Optional[str] = None
    is_batch_fully_allocated: bool = False
    is_destination_capacity_binding: bool = False
    expected_unmet_delta: float = 0.0
    expected_waste_delta: float = 0.0


class PlanLineExplanation(BaseModel):
    """Explanation containing verified evidence dictionary and controlled template sentence."""

    evidence: PlanLineEvidence
    sentence: str


class PlanLineItem(BaseModel):
    """One planned shipment line from warehouse batch to destination."""

    line_id: str
    warehouse_id: str
    batch_id: str
    sku_id: str
    dest_id: str
    quantity: int
    arrival_date: str
    remaining_life_at_arrival_days: int
    min_required_life_days: int
    freight_cost: float
    explanation: PlanLineExplanation


class PlanResponse(BaseModel):
    """Response returned by POST /api/plan."""

    status: str
    run_id: str
    origin_date: str
    solver_status: str
    solver_runtime_seconds: float
    checker_status: CheckerStatus
    summary: PlanSummary
    plan_lines: list[PlanLineItem]
