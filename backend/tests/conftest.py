"""
Optiqo — Pytest Conftest
Shared fixtures for all unit and API tests.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path so `backend.*` imports resolve
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings
from backend.data.synthetic_generator import generate_dataset
from backend.main import app


@pytest.fixture(autouse=True)
def isolate_generated_backend_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)


# ── Dataset fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def clean_dataset_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Generate a clean, valid synthetic dataset with seed=42 in a temp directory.
    Session-scoped: generated once and reused across all tests in the session.
    """
    data_dir = tmp_path_factory.mktemp("optiqo_clean_data")
    generate_dataset(output_dir=data_dir, seed=42)
    return data_dir


@pytest.fixture(scope="session")
def clean_dataset_dir_seed2(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Same as clean_dataset_dir but with seed=99, for reproducibility tests."""
    data_dir = tmp_path_factory.mktemp("optiqo_clean_data_seed99")
    generate_dataset(output_dir=data_dir, seed=99)
    return data_dir


@pytest.fixture()
def corrupted_dataset_dir(clean_dataset_dir: Path, tmp_path: Path) -> Path:
    """
    Copies the clean dataset to a fresh temp directory for per-test mutation.
    Each test that needs to inject faults gets its own copy.
    """
    dest = tmp_path / "dataset"
    shutil.copytree(str(clean_dataset_dir), str(dest))
    return dest


# ── Planning date ─────────────────────────────────────────────────────────────

@pytest.fixture()
def planning_date() -> date:
    """
    Returns the evaluation-window start date for seed=42 dataset.
    Day 365 of the 420-day dataset (start_date=2024-01-01).
    """
    return date(2024, 1, 1) + timedelta(days=364)


# ── API client ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """FastAPI test client. Module-scoped to avoid repeated app creation."""
    return TestClient(app, raise_server_exceptions=True)
