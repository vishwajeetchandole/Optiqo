"""
Optiqo — Risk Schemas
Pydantic schemas for GET /api/risk (PRD §5.1 P0-07, §10.6).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    """Alert severity levels defined in PRD §10.6."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskAlertItem(BaseModel):
    """One inventory or supply risk alert for a destination-SKU pair (PRD §10.6)."""

    dest_id: str = Field(description="Destination identifier.")
    sku_id: str = Field(description="SKU identifier.")
    severity: RiskSeverity = Field(description="HIGH | MEDIUM | LOW based on unmet share and expiry thresholds.")
    financial_exposure: float = Field(description="Total monetary exposure in currency: expected unmet margin + expiry loss.")
    days_of_cover: float = Field(description="Usable on-hand inventory divided by mean daily demand (days).")
    expected_unmet_units: float = Field(description="Scenario-weighted expected unmet demand units.")
    unmet_share_pct: float = Field(description="Expected unmet demand as a percentage of total expected demand.")
    expected_expiry_units: float = Field(description="Scenario-weighted expected units expiring unsold within the horizon.")
    expected_expiry_loss_cost: float = Field(description="Financial loss from expired units valued at unit_cost.")
    excess_units: int = Field(default=0, description="Units exceeding 14 days of cover at the end of the horizon.")
    is_supply_shortage: bool = Field(default=False, description="True if total network usable stock is below total network demand.")
    primary_driver: str = Field(description="Human-readable explanation of the primary risk driver.")


class RiskOverviewResponse(BaseModel):
    """Response payload for GET /api/risk."""

    origin_date: str = Field(description="ISO-8601 planning/evaluation origin date (YYYY-MM-DD).")
    total_alerts: int = Field(description="Total count of active risk alerts.")
    high_severity_count: int = Field(description="Count of HIGH severity alerts.")
    medium_severity_count: int = Field(description="Count of MEDIUM severity alerts.")
    low_severity_count: int = Field(description="Count of LOW severity alerts.")
    supply_shortage_skus: list[str] = Field(default_factory=list, description="SKU IDs with network-wide supply deficits.")
    alerts: list[RiskAlertItem] = Field(default_factory=list, description="Ranked risk alerts.")
