
"""Optiqo dataset table schemas, aligned with PRD section 11.1."""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# 1. skus


class SKURecord(BaseModel):
    """One row from skus.csv. Primary key: sku_id."""

    sku_id: str = Field(description="Unique SKU identifier.")
    name: str = Field(description="Human-readable SKU name.")
    category: str = Field(description="Product category.")
    shelf_life_days: int = Field(gt=0)
    min_life_days: int = Field(ge=0)
    unit_volume: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    unit_margin: float = Field(ge=0)
    case_size: Optional[int] = Field(default=None, ge=1)


# 2. warehouses


class WarehouseRecord(BaseModel):
    """One row from warehouses.csv. Primary key: warehouse_id."""

    warehouse_id: str = Field(description="Unique warehouse identifier.")
    name: str
    region: str
    capacity: Optional[float] = Field(default=None, gt=0)


# 3. destinations


DESTINATION_TYPES = {"distributor", "store"}


class DestinationRecord(BaseModel):
    """One row from destinations.csv. Primary key: dest_id."""

    dest_id: str
    name: str
    type: str
    region: str
    storage_capacity: float = Field(gt=0)
    size_tier: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_destination_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in DESTINATION_TYPES:
            raise ValueError(
                f"type must be one of {sorted(DESTINATION_TYPES)}, "
                f"got {value!r}"
            )
        return normalized


# 4. lanes


class LaneRecord(BaseModel):
    """One row from lanes.csv. Composite key: warehouse_id, dest_id."""

    warehouse_id: str
    dest_id: str
    distance_km: float = Field(gt=0)
    transit_days: int = Field(ge=1)
    freight_rate: float = Field(gt=0)
    blocked: Optional[bool] = False
    truck_capacity: Optional[float] = Field(default=None, gt=0)
    truck_fixed_cost: Optional[float] = Field(default=None, ge=0)


# 5. sales_daily


class SalesDailyRecord(BaseModel):
    """One row from sales_daily.csv. Composite key: date, dest_id, sku_id."""

    model_config = {"populate_by_name": True}

    # Use sale_date internally to avoid shadowing the datetime.date type.
    # The CSV column remains named "date".
    sale_date: datetime.date = Field(
        alias="date",
        description="Calendar date in ISO-8601 YYYY-MM-DD format.",
    )
    dest_id: str
    sku_id: str
    units_sold: float = Field(ge=0)
    price: Optional[float] = Field(default=None, ge=0)
    promo_flag: Optional[bool] = None


# 6. inventory_batches


LOCATION_TYPES = {"warehouse", "destination"}


class InventoryBatchRecord(BaseModel):
    """One row from inventory_batches.csv."""

    model_config = {"populate_by_name": True}

    location_id: str
    sku_id: str
    batch_id: str
    location_type: str
    quantity: float = Field(ge=0)
    expiry_date: datetime.date
    received_date: Optional[datetime.date] = None

    @field_validator("location_type")
    @classmethod
    def validate_location_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in LOCATION_TYPES:
            raise ValueError(
                f"location_type must be one of {sorted(LOCATION_TYPES)}, "
                f"got {value!r}"
            )
        return normalized


# 7. inbound_shipments


class InboundShipmentRecord(BaseModel):
    """One row from inbound_shipments.csv. Primary key: shipment_id."""

    shipment_id: str
    dest_id: str
    sku_id: str
    batch_id: str
    quantity: float = Field(ge=0)
    arrival_date: datetime.date
    expiry_date: datetime.date


# 8. warehouse_receipts


class WarehouseReceiptRecord(BaseModel):
    """One row from warehouse_receipts.csv. Primary key: receipt_id."""

    receipt_id: str
    warehouse_id: str
    sku_id: str
    batch_id: str
    quantity: float = Field(ge=0)
    arrival_date: datetime.date
    expiry_date: datetime.date


# 9. calendar_events


class CalendarEventRecord(BaseModel):
    """One row from calendar_events.csv. Primary key: date."""

    model_config = {"populate_by_name": True}

    event_date: datetime.date = Field(alias="date")
    festival_flag: bool
    promotion_flag: Optional[bool] = None
    weather_index: Optional[float] = None


# 10. config


class ConfigRecord(BaseModel):
    """Planning configuration values."""

    shortage_penalty_factor: float = Field(default=1.5, gt=0)
    holding_cost_rate: float = Field(default=0.02, gt=0)
    horizon: int = Field(default=7, ge=1)
    baseline_safety_days: int = Field(default=2, ge=0)

    scenario_weight_low: Optional[float] = Field(
        default=0.3, ge=0, le=1
    )
    scenario_weight_mid: Optional[float] = Field(
        default=0.4, ge=0, le=1
    )
    scenario_weight_high: Optional[float] = Field(
        default=0.3, ge=0, le=1
    )

    @model_validator(mode="after")
    def validate_scenario_weights(self) -> "ConfigRecord":
        weights = (
            self.scenario_weight_low,
            self.scenario_weight_mid,
            self.scenario_weight_high,
        )

        # If all scenario weights are omitted/null, allow the model defaults
        # or explicit nulls. If supplied, the total must equal 1.
        if any(weight is None for weight in weights):
            if all(weight is None for weight in weights):
                return self
            raise ValueError(
                "Provide all three scenario weights, or omit all three."
            )

        total = sum(weights)
        if abs(total - 1.0) > 1e-4:
            raise ValueError(
                f"Scenario weights must sum to 1.0; got {total}."
            )

        return self


class DatasetValidationIssue(BaseModel):
    """One issue found while validating a user-uploaded dataset."""

    level: str = Field(description="Issue severity: error, warning, or info.")
    code: str = Field(description="Machine readable validation code.")
    message: str = Field(description="Human readable issue description.")
    row_index: Optional[int] = Field(default=None, description="Zero-based row index, when applicable.")
    column: Optional[str] = Field(default=None, description="Column name involved, when applicable.")


class DatasetValidationReport(BaseModel):
    """Validation result for dataset inspection or upload validation."""

    status: str = Field(description="VALID | WARNINGS_ONLY | INVALID")
    valid: bool = Field(description="True when the dataset passed validation without blocking errors.")
    issue_count: int = Field(description="Total number of issues reported.")
    errors: int = Field(description="Number of blocking errors.")
    warnings: int = Field(description="Number of warnings.")
    issues: list[DatasetValidationIssue] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    """Metadata describing an uploaded dataset snapshot."""

    dataset_id: str = Field(description="Stable ID for the dataset in the upload registry.")
    name: str = Field(description="Friendly dataset name.")
    original_name: str = Field(description="Filename received from the client.")
    file_size_bytes: int = Field(description="Original file size in bytes.")
    row_count: int = Field(description="Total rows in the dataset file.")
    column_count: int = Field(description="Number of columns detected in the uploaded file.")
    columns: list[str] = Field(default_factory=list, description="Column names detected in the file.")
    source_type: str = Field(description="File type, such as csv or excel.")
    status: str = Field(default="READY", description="Dataset lifecycle status.")
    validation_status: str = Field(default="VALID", description="Validation status.")
    active: bool = Field(default=False, description="True for the dataset currently marked active.")
    uploaded_at: datetime.datetime = Field(description="UTC timestamp when the dataset was uploaded.")
    file_path: Optional[str] = Field(default=None, description="Server-side storage path for the uploaded file.")
    preview_url: Optional[str] = Field(default=None, description="Preview endpoint for the dataset.")


class DatasetListResponse(BaseModel):
    datasets: list[DatasetMetadata] = Field(default_factory=list)
    active_dataset_id: Optional[str] = Field(default=None)


class DatasetUploadResponse(DatasetMetadata):
    pass


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str]
    row_count: int
    preview_rows: list[dict[str, object]] = Field(default_factory=list)
