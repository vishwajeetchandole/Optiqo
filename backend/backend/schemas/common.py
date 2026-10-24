"""
Optiqo — Common Schemas
Shared enums, status codes, and RFC 7807 Problem Details response model.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Status Enums ─────────────────────────────────────────────────────────────

class AppStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"


class ComponentStatus(str, Enum):
    OK = "OK"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    LOADED = "LOADED"
    NOT_LOADED = "NOT_LOADED"


class DatasetStatus(str, Enum):
    READY = "READY"
    NOT_GENERATED = "NOT_GENERATED"
    GENERATING = "GENERATING"


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNINGS_ONLY = "WARNINGS_ONLY"


class PlanStatus(str, Enum):
    OK = "OK"
    SOLVER_TIMEOUT = "SOLVER_TIMEOUT"
    SOLVER_NOT_OPTIMAL = "SOLVER_NOT_OPTIMAL"
    INFEASIBLE = "INFEASIBLE"
    CHECK_FAILED = "CHECK_FAILED"
    FALLBACK_FORECAST = "FALLBACK_FORECAST"
    ERROR_DATA = "ERROR_DATA"


# ── RFC 7807 Problem Details ──────────────────────────────────────────────────

class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response for API errors."""

    type: str = Field(
        default="about:blank",
        description="A URI reference identifying the problem type.",
        examples=["https://optiqo.vyrox.ai/errors/VALIDATION_FAILED"],
    )
    title: str = Field(
        description="Short, human-readable summary of the problem type.",
        examples=["Data Validation Failed"],
    )
    status: int = Field(
        description="HTTP status code.",
        examples=[422],
    )
    detail: str = Field(
        description="Human-readable explanation of this specific occurrence.",
        examples=["2 blocking errors detected in dataset."],
    )
    instance: Optional[str] = Field(
        default=None,
        description="URI reference of the specific request that caused the problem.",
        examples=["/api/data/validate"],
    )
    code: str = Field(
        description="Machine-readable error code.",
        examples=["VALIDATION_FAILED"],
    )
    errors: Optional[list[Any]] = Field(
        default=None,
        description="Structured list of sub-errors (field-level validation items).",
    )
