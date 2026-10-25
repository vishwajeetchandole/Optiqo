"""Schemas for the selected-run distribution network map."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LocationRisk(BaseModel):
    basis: Literal["pre-plan"] = "pre-plan"
    level: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    alert_count: int = 0
    expected_unmet_units: Optional[float] = None
    expected_expiry_units: Optional[float] = None
    minimum_days_of_cover: Optional[float] = None
    primary_drivers: list[str] = Field(default_factory=list)


class NetworkLocation(BaseModel):
    id: str
    type: Literal["warehouse", "distributor", "store"]
    name: str
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_status: Literal["valid", "missing", "invalid"]
    usable_inventory: Optional[float] = None
    risk: Optional[LocationRisk] = None


class ShipmentFlow(BaseModel):
    line_id: str
    source_id: str
    destination_id: str
    sku_id: str
    quantity: float
    freight_cost: Optional[float] = None
    verification_status: Literal["verified", "unverified"]


class NetworkMapResponse(BaseModel):
    dataset_id: str
    dataset_hash: str
    run_id: str
    origin_date: str
    locations: list[NetworkLocation]
    flows: list[ShipmentFlow]
