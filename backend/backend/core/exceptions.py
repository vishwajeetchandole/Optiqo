"""
Optiqo — Domain Exception Hierarchy
All application-level errors descend from OptiqoError so the
FastAPI exception handler can emit consistent RFC 7807 payloads.
"""

from __future__ import annotations


class OptiqoError(Exception):
    """Base class for all Optiqo backend errors."""

    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


# ── Data & Validation Errors ──────────────────────────────────────────────────

class DataError(OptiqoError):
    """Dataset-level problem (missing file, missing column, bad data)."""
    http_status = 422
    error_code = "ERROR_DATA"


class ValidationError(DataError):
    """Raised when the 13-fault validation engine detects blocking errors."""
    http_status = 422
    error_code = "VALIDATION_FAILED"


class MissingDatasetError(DataError):
    """Raised when the demo dataset has not been generated yet."""
    http_status = 404
    error_code = "DATASET_NOT_FOUND"


# ── Engine Errors ─────────────────────────────────────────────────────────────

class ForecastError(OptiqoError):
    """Raised when the forecasting engine encounters an unrecoverable failure."""
    http_status = 500
    error_code = "FORECAST_ERROR"


class SolverTimeoutError(OptiqoError):
    """Raised when PuLP/CBC exceeds the configured time limit."""
    http_status = 500
    error_code = "SOLVER_TIMEOUT"


class SolverNotOptimalError(OptiqoError):
    """Raised when the solver finishes in a non-optimal, non-infeasible state."""
    http_status = 500
    error_code = "SOLVER_NOT_OPTIMAL"


class InfeasibleError(OptiqoError):
    """Raised when the LP is infeasible (P1 features; P0 should always be feasible)."""
    http_status = 422
    error_code = "INFEASIBLE"


class ConstraintCheckFailedError(OptiqoError):
    """Raised when the independent constraint verifier rejects a plan."""
    http_status = 422
    error_code = "CHECK_FAILED"


# ── Run / Storage Errors ──────────────────────────────────────────────────────

class RunNotFoundError(OptiqoError):
    """Raised when a requested run_id does not exist in storage."""
    http_status = 404
    error_code = "RUN_NOT_FOUND"
