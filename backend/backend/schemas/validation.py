"""
Optiqo — Validation Report Schemas
Request and response models for POST /api/data/validate.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from backend.schemas.common import ValidationStatus


def _to_serializable(val: Any) -> Any:
    """Recursively convert numpy/pandas scalars/structures to native Python types."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {str(k): _to_serializable(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_serializable(v) for v in val]
    if isinstance(val, set):
        return [_to_serializable(v) for v in sorted(val, key=str)]
    if hasattr(val, "item") and callable(getattr(val, "item")):
        try:
            return val.item()
        except Exception:
            pass
    if hasattr(val, "isoformat") and callable(getattr(val, "isoformat")):
        return val.isoformat()
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


class FaultType(str, Enum):
    """The 13 fault types defined in PRD §11.2 (P0-02)."""

    MISSING_FILE = "MISSING_FILE"                          # 1
    MISSING_COLUMN = "MISSING_COLUMN"                      # 2
    MISSING_VALUE = "MISSING_VALUE"                        # 3
    NON_NUMERIC_OR_NEGATIVE_QUANTITY = "NON_NUMERIC_OR_NEGATIVE_QUANTITY"  # 4
    INVALID_DATE = "INVALID_DATE"                          # 5
    DUPLICATE_KEY = "DUPLICATE_KEY"                        # 6
    UNKNOWN_SKU = "UNKNOWN_SKU"                            # 7
    UNKNOWN_WAREHOUSE = "UNKNOWN_WAREHOUSE"                # 8
    UNKNOWN_DESTINATION = "UNKNOWN_DESTINATION"            # 9
    EXPIRED_BATCH = "EXPIRED_BATCH"                        # 10
    NON_POSITIVE_STORAGE_CAPACITY = "NON_POSITIVE_STORAGE_CAPACITY"  # 11
    NON_POSITIVE_UNIT_VOLUME = "NON_POSITIVE_UNIT_VOLUME"  # 12
    TRANSIT_DAYS_BELOW_ONE = "TRANSIT_DAYS_BELOW_ONE"      # 13


class WarningType(str, Enum):
    """Warning types that allow planning to continue (PRD §11.2)."""

    SALES_GAP = "SALES_GAP"
    EXTREME_OUTLIER = "EXTREME_OUTLIER"
    STOCK_EXCEEDS_CAPACITY = "STOCK_EXCEEDS_CAPACITY"


class ValidationFinding(BaseModel):
    """One error or warning item in the validation report."""

    table: str = Field(description="Name of the affected CSV table.")
    row_index: Optional[int] = Field(default=None, description="0-based row index in the CSV (null for file-level errors).")
    field: Optional[str] = Field(default=None, description="Column name involved (null for row-level errors).")
    rule: str = Field(description="Machine-readable fault or warning type code.")
    message: str = Field(description="Human-readable plain-language explanation.")
    observed_value: Optional[Any] = Field(default=None, description="The problematic value (if scalar).")

    @field_validator("row_index", mode="before")
    @classmethod
    def _coerce_row_index(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        return int(v)

    @field_validator("observed_value", mode="before")
    @classmethod
    def _coerce_observed_value(cls, v: Any) -> Any:
        return _to_serializable(v)


class ValidationRequest(BaseModel):
    """Body for POST /api/data/validate."""

    dataset_path: Optional[str] = Field(
        default=None,
        description="Path to the folder containing the 10 CSV tables. Defaults to demo_data if omitted.",
    )
    planning_date: Optional[str] = Field(
        default=None,
        description="ISO-8601 date used to flag expired batches (fault type 10). Defaults to today.",
    )
    exclude_expired_batches: bool = Field(
        default=True,
        description="If True, expired batches trigger an error (blocking). If False, they are listed as warnings.",
    )


class ValidationSummary(BaseModel):
    """Aggregate counts for the validation report."""

    total_tables_checked: int
    checked_at: datetime


class ValidationReportResponse(BaseModel):
    """Response body for POST /api/data/validate."""

    status: ValidationStatus = Field(
        description="VALID | WARNINGS_ONLY | INVALID"
    )
    planning_blocked: bool = Field(
        description="True when there is at least one blocking error."
    )
    error_count: int = Field(description="Number of blocking errors.")
    warning_count: int = Field(description="Number of non-blocking warnings.")
    errors: list[ValidationFinding] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    summary: ValidationSummary
