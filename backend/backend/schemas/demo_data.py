"""
Optiqo — Demo Dataset Response Schema
Response body for GET /api/demo-data.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import DatasetStatus


class TableMetadata(BaseModel):
    """Row and file-size summary for one CSV table."""

    row_count: int
    file_size_bytes: int


class DatasetGenerationParams(BaseModel):
    """Parameters used to generate the demo dataset."""

    warehouses_count: int
    destinations_count: int
    skus_count: int
    days_count: int
    seed: int


class DemoDataResponse(BaseModel):
    """Response body for GET /api/demo-data."""

    status: DatasetStatus
    dataset_id: str = Field(description="Stable identifier for the generated dataset, e.g. 'demo_seed_42'.")
    dataset_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of the concatenated CSV contents for reproducibility verification.",
    )
    parameters: DatasetGenerationParams
    tables: Dict[str, TableMetadata] = Field(
        description="Per-table metadata keyed by table name."
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable status message (e.g. 'Dataset generated.' or 'Dataset loaded from cache.').",
    )
