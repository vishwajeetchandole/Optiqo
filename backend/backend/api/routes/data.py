"""
Optiqo — Data Routes
  GET  /api/demo-data       → Generate or load the default demo dataset
  POST /api/data/validate   → Run the 13-fault validation engine
"""

from __future__ import annotations

import io
import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, Query, UploadFile

from backend.core.config import settings
from backend.core.exceptions import DataError, MissingDatasetError
from backend.core.logging import get_logger
from backend.data.loader import TABLE_NAMES
from backend.data.synthetic_generator import compute_dataset_hash, generate_dataset
from backend.data.validator import validate_dataset
from backend.schemas.common import DatasetStatus, ValidationStatus
from backend.schemas.dataset import DatasetListResponse, DatasetMetadata, DatasetPreviewResponse, DatasetUploadResponse, DatasetValidationIssue, DatasetValidationReport
from backend.schemas.demo_data import DatasetGenerationParams, DemoDataResponse, TableMetadata
from backend.schemas.validation import ValidationRequest, ValidationReportResponse, ValidationSummary

logger = get_logger(__name__)
router = APIRouter()

ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _upload_root() -> Path:
    root = settings.uploads_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dataset_manifest_path(dataset_id: str) -> Path:
    return _upload_root() / dataset_id / "manifest.json"


def _safe_dataset_id(base_name: str | None) -> str:
    slug = (base_name or "dataset").strip()
    slug = Path(slug).stem or "dataset"
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in slug)
    slug = slug.strip("-_") or "dataset"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _safe_original_name(filename: str | None) -> str:
    if not filename:
        raise DataError("A filename is required for upload.")
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise DataError("The uploaded filename is invalid.")
    return safe_name


def _read_uploaded_frame(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    lower_name = file_name.lower()
    if lower_name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), low_memory=False)
        except Exception as exc:  # pragma: no cover - error path
            raise DataError(f"Could not parse CSV file '{file_name}': {exc}") from exc

    if lower_name.endswith((".xlsx", ".xls")):
        try:
            if lower_name.endswith(".xlsx"):
                return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
            return pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
        except ImportError as exc:
            raise DataError(
                "Excel support is not available in this environment. Install openpyxl for .xlsx files or xlrd for .xls files."
            ) from exc
        except Exception as exc:  # pragma: no cover - error path
            raise DataError(f"Could not parse Excel file '{file_name}': {exc}") from exc

    raise DataError(f"Unsupported file type '{file_name}'. Only CSV, XLSX, and XLS files are accepted.")


def _serialize_preview_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    return value


def _validate_uploaded_dataframe(df: pd.DataFrame) -> DatasetValidationReport:
    issues: list[DatasetValidationIssue] = []
    required_columns = ["date", "sku", "product", "product_id", "warehouse", "warehouse_id", "demand", "inventory", "units_sold"]
    normalized = {str(col).strip().lower(): str(col) for col in df.columns}
    available = set(normalized)
    missing = [col for col in required_columns if col not in available and not any(candidate in available for candidate in (col, f"{col}s"))]
    if missing:
        issues.append(DatasetValidationIssue(
            level="warning",
            code="MISSING_SUGGESTED_COLUMNS",
            message="The file is missing common forecasting columns; you may need to map the dataset before use.",
            column=missing[0],
        ))

    if df.empty:
        issues.append(DatasetValidationIssue(level="error", code="EMPTY_DATASET", message="The uploaded dataset is empty."))

    duplicate_rows = df.duplicated(keep=False).sum()
    if duplicate_rows:
        issues.append(DatasetValidationIssue(level="warning", code="DUPLICATE_ROWS", message=f"{duplicate_rows} duplicate rows were found in the uploaded file.", row_index=int(df.duplicated(keep=False).idxmax()) if not df.empty else None))

    null_ratio = df.isna().sum().sum() / max(1, df.size)
    if null_ratio > 0.25:
        issues.append(DatasetValidationIssue(level="warning", code="HIGH_NULL_RATIO", message=f"{null_ratio * 100:.1f}% of uploaded values are blank or missing."))

    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = sum(1 for issue in issues if issue.level == "warning")
    status = ValidationStatus.VALID if not errors else ValidationStatus.INVALID
    if errors == 0 and warnings > 0:
        status = ValidationStatus.WARNINGS_ONLY

    return DatasetValidationReport(
        status=status,
        valid=errors == 0,
        issue_count=len(issues),
        errors=errors,
        warnings=warnings,
        issues=issues,
    )


def _read_dataset_manifest(dataset_id: str) -> dict[str, Any]:
    manifest_path = _dataset_manifest_path(dataset_id)
    if not manifest_path.exists():
        raise MissingDatasetError(f"Dataset '{dataset_id}' was not found on the server.")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _write_dataset_manifest(dataset_id: str, payload: dict[str, Any]) -> None:
    manifest_path = _dataset_manifest_path(dataset_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")


def _active_dataset_id() -> str | None:
    active_path = _upload_root() / "active_dataset.json"
    if not active_path.exists():
        return None
    try:
        return json.loads(active_path.read_text(encoding="utf-8")).get("dataset_id")
    except Exception:
        return None


def _set_active_dataset_id(dataset_id: str | None) -> None:
    active_path = _upload_root() / "active_dataset.json"
    if dataset_id is None:
        active_path.unlink(missing_ok=True)
        return
    active_path.write_text(json.dumps({"dataset_id": dataset_id}, indent=2), encoding="utf-8")


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


# ── Uploaded dataset registry ─────────────────────────────────────────────────

@router.get(
    "/datasets",
    response_model=DatasetListResponse,
    summary="List uploaded datasets available in the registry",
    tags=["Data"],
)
def list_datasets() -> DatasetListResponse:
    upload_root = _upload_root()
    datasets: list[DatasetMetadata] = []
    for dataset_dir in sorted(upload_root.iterdir(), key=lambda p: p.name.lower()):
        if not dataset_dir.is_dir():
            continue
        manifest_path = dataset_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        datasets.append(DatasetMetadata(**manifest))

    active_id = _active_dataset_id()
    if active_id:
        for dataset in datasets:
            dataset.active = dataset.dataset_id == active_id

    return DatasetListResponse(datasets=datasets, active_dataset_id=active_id)


@router.get(
    "/datasets/active",
    response_model=DatasetMetadata | None,
    summary="Get the currently active dataset",
    tags=["Data"],
)
def get_active_dataset() -> DatasetMetadata | None:
    active_id = _active_dataset_id()
    if not active_id:
        return None
    return DatasetMetadata(**_read_dataset_manifest(active_id))


@router.post(
    "/datasets/upload",
    response_model=DatasetUploadResponse,
    summary="Upload a CSV or Excel dataset",
    tags=["Data"],
)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str | None = Form(default=None),
    replace_existing: bool = Form(default=False),
) -> DatasetUploadResponse:
    safe_name = _safe_original_name(file.filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise DataError("Unsupported file type. Only CSV, XLSX, and XLS files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise DataError("Uploaded file is empty.")
    if len(file_bytes) > settings.MAX_UPLOAD_FILE_SIZE_BYTES:
        raise DataError(
            f"File is too large. Maximum supported size is {settings.MAX_UPLOAD_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB."
        )

    dataset_id = _safe_dataset_id(dataset_name or safe_name)
    upload_dir = _upload_root() / dataset_id
    if upload_dir.exists() and not replace_existing:
        raise DataError(f"A dataset with the generated ID '{dataset_id}' already exists. Please retry the upload.")
    upload_dir.mkdir(parents=True, exist_ok=True)

    target_path = upload_dir / safe_name
    target_path.write_bytes(file_bytes)

    df = _read_uploaded_frame(safe_name, file_bytes)
    validation = _validate_uploaded_dataframe(df)
    preview_rows = df.head(20).replace({pd.NA: None, pd.NaT: None}).to_dict(orient="records")
    preview_rows = [{str(k): _serialize_preview_value(v) for k, v in row.items()} for row in preview_rows]

    payload: dict[str, Any] = {
        "dataset_id": dataset_id,
        "name": dataset_name or Path(safe_name).stem,
        "original_name": safe_name,
        "file_size_bytes": len(file_bytes),
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(column) for column in df.columns],
        "source_type": suffix.lstrip("."),
        "status": DatasetStatus.READY.value,
        "validation_status": validation.status.value,
        "active": False,
        "uploaded_at": datetime.now(tz=timezone.utc).isoformat(),
        "file_path": str(target_path),
        "preview_url": f"/api/datasets/{dataset_id}/preview",
    }

    _write_dataset_manifest(dataset_id, payload)
    return DatasetUploadResponse(**payload)


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetMetadata,
    summary="Read dataset metadata for an uploaded dataset",
    tags=["Data"],
)
def get_dataset(dataset_id: str) -> DatasetMetadata:
    manifest = _read_dataset_manifest(dataset_id)
    return DatasetMetadata(**manifest)


@router.get(
    "/datasets/{dataset_id}/preview",
    response_model=DatasetPreviewResponse,
    summary="Get preview rows for a dataset",
    tags=["Data"],
)
def preview_dataset(dataset_id: str, limit: int = Query(default=20, ge=1, le=100)) -> DatasetPreviewResponse:
    manifest = _read_dataset_manifest(dataset_id)
    file_path = Path(manifest["file_path"])
    if not file_path.exists():
        raise MissingDatasetError(f"Dataset '{dataset_id}' is missing its underlying file on disk.")

    df = _read_uploaded_frame(file_path.name, file_path.read_bytes())
    preview_rows = df.head(limit).replace({pd.NA: None, pd.NaT: None}).to_dict(orient="records")
    preview_rows = [{str(k): _serialize_preview_value(v) for k, v in row.items()} for row in preview_rows]
    return DatasetPreviewResponse(
        dataset_id=dataset_id,
        columns=[str(column) for column in df.columns],
        row_count=int(len(df)),
        preview_rows=preview_rows,
    )


@router.post(
    "/datasets/{dataset_id}/validate",
    response_model=DatasetValidationReport,
    summary="Validate an uploaded dataset file",
    tags=["Data"],
)
def validate_uploaded_dataset(dataset_id: str) -> DatasetValidationReport:
    manifest = _read_dataset_manifest(dataset_id)
    file_path = Path(manifest["file_path"])
    if not file_path.exists():
        raise MissingDatasetError(f"Dataset '{dataset_id}' is missing its underlying file on disk.")

    df = _read_uploaded_frame(file_path.name, file_path.read_bytes())
    result = _validate_uploaded_dataframe(df)
    manifest["validation_status"] = result.status.value
    _write_dataset_manifest(dataset_id, manifest)
    return result


@router.post(
    "/datasets/{dataset_id}/activate",
    response_model=DatasetMetadata,
    summary="Mark an uploaded dataset as the active dataset",
    tags=["Data"],
)
def activate_dataset(dataset_id: str) -> DatasetMetadata:
    manifest = _read_dataset_manifest(dataset_id)
    for dataset_dir in _upload_root().iterdir():
        if dataset_dir.is_dir():
            manifest_path = dataset_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    current = json.loads(manifest_path.read_text(encoding="utf-8"))
                    current["active"] = current.get("dataset_id") == dataset_id
                    _write_dataset_manifest(current["dataset_id"], current)
                except Exception:
                    continue

    manifest["active"] = True
    _write_dataset_manifest(dataset_id, manifest)
    _set_active_dataset_id(dataset_id)
    return DatasetMetadata(**manifest)
