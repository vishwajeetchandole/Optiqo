"""
Optiqo — Data Routes
  GET  /api/demo-data       → Generate or load the default demo dataset
  POST /api/data/validate   → Run the 13-fault validation engine
"""

from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from backend.core.config import settings
from backend.core.exceptions import DataError, MissingDatasetError
from backend.core.logging import get_logger
from backend.data.loader import TABLE_NAMES
from backend.data.synthetic_generator import compute_dataset_hash, generate_dataset
from backend.data.validator import validate_dataset
from backend.schemas.common import DatasetStatus, ValidationStatus
from backend.schemas.demo_data import DatasetGenerationParams, DemoDataResponse, TableMetadata
from backend.schemas.validation import ValidationRequest, ValidationReportResponse, ValidationSummary

logger = get_logger(__name__)
router = APIRouter()


# ── GET /api/demo-data ────────────────────────────────────────────────────────

@router.get(
    "/demo-data",
    response_model=DemoDataResponse,
    summary="Load or generate the default demo dataset",
    description=(
        "Returns metadata about the default synthetic FMCG dataset. "
        "If the CSVs do not exist yet (or force_regenerate=true), they are generated deterministically "
        "from the given seed. The same seed always produces byte-identical CSVs (PRD §S2). "
        "Each seed is cached in its own sub-directory so different seeds never overwrite each other."
    ),
    tags=["Data"],
)
def get_demo_data(
    seed: int = Query(default=settings.DEFAULT_SEED, ge=0, description="Random seed for reproducible generation."),
    force_regenerate: bool = Query(
        default=False,
        description="If true, delete and regenerate the dataset for THIS seed (other seeds are untouched).",
    ),
) -> DemoDataResponse:
    # Each seed gets its own isolated subdirectory so seeds never overwrite each other.
    demo_dir = settings.demo_data_dir / f"seed_{seed}"

    if force_regenerate and demo_dir.exists():
        shutil.rmtree(demo_dir)
        logger.info("Cleared demo_data/seed_%d for forced regeneration.", seed)

    existing_csvs = list(demo_dir.glob("*.csv")) if demo_dir.exists() else []
    needs_generation = len(existing_csvs) < 10

    if needs_generation:
        logger.info("Generating demo dataset (seed=%d) into %s...", seed, demo_dir)
        generate_dataset(output_dir=demo_dir, seed=seed)
        message = f"Dataset generated with seed={seed}."
    else:
        message = f"Dataset loaded from cache (seed={seed})."
        logger.info(message)

    # Build per-table metadata (count rows by newline-counting — avoids loading full CSVs into memory)
    table_meta: dict[str, TableMetadata] = {}
    for table_name in TABLE_NAMES:
        csv_path = demo_dir / f"{table_name}.csv"
        if csv_path.exists():
            row_count = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1  # minus header
            table_meta[table_name] = TableMetadata(
                row_count=max(0, row_count),
                file_size_bytes=csv_path.stat().st_size,
            )

    dataset_id = f"demo_seed_{seed}"
    dataset_hash = compute_dataset_hash(demo_dir)

    return DemoDataResponse(
        status=DatasetStatus.READY,
        dataset_id=dataset_id,
        dataset_hash=dataset_hash,
        parameters=DatasetGenerationParams(
            warehouses_count=settings.N_WAREHOUSES,
            destinations_count=settings.N_DESTINATIONS,
            skus_count=settings.N_SKUS,
            days_count=settings.N_DAYS,
            seed=seed,
        ),
        tables=table_meta,
        message=message,
    )


# ── POST /api/data/validate ───────────────────────────────────────────────────

@router.post(
    "/data/validate",
    response_model=ValidationReportResponse,
    summary="Run 13-fault data validation",
    description=(
        "Validates all 10 CSV tables against the PRD §11.2 rules. "
        "Returns a full report of blocking errors and non-blocking warnings. "
        "If planning_blocked=true, all downstream endpoints requiring valid data will also refuse to run."
    ),
    tags=["Data"],
)
def validate_data(body: ValidationRequest) -> ValidationReportResponse:
    # Resolve dataset path: prefer explicit path, otherwise fall back to the seed-specific demo cache
    if body.dataset_path:
        data_dir = Path(body.dataset_path)
        if not data_dir.is_absolute():
            data_dir = settings.BASE_DIR / body.dataset_path
    else:
        # Default: the seed_42 demo cache (the canonical default dataset)
        data_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"

    if not data_dir.exists():
        raise MissingDatasetError(
            message=f"Dataset directory not found: {data_dir}. "
                    "Call GET /api/demo-data first to generate the demo dataset.",
        )

    # Parse planning date
    planning_date: Optional[date] = None
    if body.planning_date:
        try:
            planning_date = date.fromisoformat(body.planning_date)
        except ValueError:
            raise DataError(
                message=f"Invalid planning_date format: '{body.planning_date}'. Expected ISO-8601 YYYY-MM-DD."
            )

    logger.info(
        "Validating dataset at %s (planning_date=%s, exclude_expired=%s)",
        data_dir, planning_date or "today", body.exclude_expired_batches,
    )

    errors, warnings = validate_dataset(
        data_dir=data_dir,
        planning_date=planning_date,
        exclude_expired_batches=body.exclude_expired_batches,
    )

    planning_blocked = len(errors) > 0

    if planning_blocked:
        validation_status = ValidationStatus.INVALID
    elif warnings:
        validation_status = ValidationStatus.WARNINGS_ONLY
    else:
        validation_status = ValidationStatus.VALID

    logger.info(
        "Validation complete: status=%s errors=%d warnings=%d",
        validation_status, len(errors), len(warnings),
    )

    return ValidationReportResponse(
        status=validation_status,
        planning_blocked=planning_blocked,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
        summary=ValidationSummary(
            total_tables_checked=len(TABLE_NAMES),
            checked_at=datetime.now(tz=timezone.utc),
        ),
    )
