"""
Optiqo — Run Storage & Manifest Repository (PRD §5.1 P0-11, §6.7, Plan §4.8, Phase 7)

Provides file-based storage of run manifests in settings.runs_dir:
- compute_dataset_hash: SHA-256 fingerprint over dataset files
- get_software_versions: versions of runtime libraries
- save_run: persists run manifest to {run_id}.json
- get_run: loads run manifest by run_id (raises RunNotFoundError if missing)
- list_runs: lists summary of all stored runs
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any, Optional

import pandas as pd
import pulp

from backend.core.config import settings
from backend.core.exceptions import RunNotFoundError
from backend.core.logging import get_logger
from backend.schemas.runs import RunManifest

logger = get_logger(__name__)


def compute_dataset_hash(data_dir: Path | str) -> str:
    """
    Compute a deterministic SHA-256 fingerprint over all CSV files in the dataset folder.
    Sorts files alphabetically and feeds content chunks into SHA-256.
    """
    path = Path(data_dir)
    if not path.exists():
        return hashlib.sha256(str(data_dir).encode("utf-8")).hexdigest()[:16]

    hasher = hashlib.sha256()
    csv_files = sorted(path.glob("*.csv"), key=lambda p: p.name)
    if not csv_files:
        hasher.update(str(data_dir).encode("utf-8"))
    else:
        for f in csv_files:
            hasher.update(f.name.encode("utf-8"))
            try:
                content = f.read_bytes()
                hasher.update(content)
            except Exception:
                hasher.update(str(f.stat().st_size).encode("utf-8"))

    return hasher.hexdigest()[:16]


def get_software_versions() -> dict[str, str]:
    """Capture version snapshot of core execution dependencies."""
    versions = {
        "optiqo": settings.APP_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "pulp": getattr(pulp, "__version__", "unknown"),
    }
    try:
        import lightgbm
        versions["lightgbm"] = getattr(lightgbm, "__version__", "unknown")
    except ImportError:
        versions["lightgbm"] = "not_installed"
    return versions


import re

SAFE_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_safe_run_id(run_id: str) -> str:
    """Validate that run_id contains only safe characters to prevent path traversal."""
    if not run_id or not isinstance(run_id, str) or not SAFE_RUN_ID_PATTERN.match(run_id):
        raise RunNotFoundError(
            message=f"Invalid run_id: '{run_id}'. Must contain only alphanumeric characters, hyphens, and underscores."
        )
    return run_id


def save_run(run_data: dict[str, Any] | RunManifest, runs_dir: Optional[Path] = None) -> Path:
    """
    Persist run manifest to JSON file in settings.runs_dir (or custom runs_dir).
    Returns path to written JSON file.
    """
    target_dir = (runs_dir or settings.runs_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(run_data, RunManifest):
        run_dict = run_data.model_dump()
    else:
        run_dict = dict(run_data)

    raw_run_id = run_dict.get("run_id")
    if not raw_run_id:
        raise ValueError("run_data must contain a non-empty 'run_id'.")

    run_id = validate_safe_run_id(raw_run_id)

    # Ensure software versions snapshot is included
    if not run_dict.get("software_versions"):
        run_dict["software_versions"] = get_software_versions()

    file_path = (target_dir / f"{run_id}.json").resolve()
    temp_path = (target_dir / f"{run_id}.tmp").resolve()

    if not str(file_path).startswith(str(target_dir)):
        raise RunNotFoundError(message=f"Invalid path traversal attempt for run_id: '{run_id}'.")

    # Atomic write
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(run_dict, f, indent=2, default=str)
    temp_path.replace(file_path)

    logger.info("Persisted run manifest: run_id=%s, path=%s", run_id, file_path)
    return file_path


def get_run(run_id: str, runs_dir: Optional[Path] = None) -> dict[str, Any]:
    """
    Retrieve run manifest by run_id from settings.runs_dir (or custom runs_dir).
    Raises RunNotFoundError (HTTP 404) if the run is not found or run_id is invalid.
    """
    valid_id = validate_safe_run_id(run_id)
    target_dir = (runs_dir or settings.runs_dir).resolve()
    file_path = (target_dir / f"{valid_id}.json").resolve()

    if not str(file_path).startswith(str(target_dir)):
        raise RunNotFoundError(message=f"Invalid path traversal attempt for run_id: '{run_id}'.")

    if not file_path.exists():
        raise RunNotFoundError(
            message=f"Run '{run_id}' not found in storage. Ensure the run was executed or specify a valid run_id."
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to read run manifest '%s': %s", file_path, e)
        raise RunNotFoundError(
            message=f"Run '{run_id}' could not be read from storage: {e}"
        )


def list_runs(runs_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    """
    List summary metadata for all stored runs, sorted newest first.
    """
    target_dir = (runs_dir or settings.runs_dir).resolve()
    if not target_dir.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for file_path in sorted(target_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                summaries.append({
                    "run_id": data.get("run_id"),
                    "run_type": data.get("run_type", "PLAN"),
                    "created_at": data.get("created_at"),
                    "origin_date": data.get("origin_date"),
                    "status": data.get("status"),
                    "dataset_hash": data.get("dataset_hash"),
                })
        except Exception:
            continue
    return summaries
