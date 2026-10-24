"""
Optiqo — Health Check Schemas
Request/response for GET /api/health.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field

from backend.schemas.common import AppStatus, ComponentStatus


class ComponentHealthDetail(BaseModel):
    status: ComponentStatus
    detail: str = ""


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""

    status: AppStatus = Field(description="Overall service health.")
    version: str = Field(description="Backend application version.")
    environment: str = Field(description="Runtime environment label (development/staging/production).")
    components: Dict[str, str] = Field(
        description="Per-component status strings."
    )
    timestamp: datetime = Field(description="Server time at which health was checked.")
