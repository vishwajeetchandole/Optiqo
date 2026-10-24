"""
Optiqo — Unit Tests: Synthetic Data Generator & Loader (PRD §11.3)

Tests:
  - All 10 required tables are generated
  - All required columns are present in each table
  - Same seed produces byte-identical CSVs (S2)
  - Different seed produces different data/hash
  - Correct row counts (30 SKUs, 4 WH, 40 dests, 160 lanes, 420 cal days)
  - Dataset hash is stable across multiple calls
  - Loader returns correct LoadedDataset with all 10 tables
  - Primary key uniqueness in all entity tables
  - Foreign key referential integrity
  - No negative quantities in generated data
  - All dates are valid ISO-8601
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from backend.data.loader import MANDATORY_COLUMNS, TABLE_NAMES, load_dataset
from backend.data.synthetic_generator import compute_dataset_hash, generate_dataset


# ── Table existence ───────────────────────────────────────────────────────────

def test_all_10_tables_exist(clean_dataset_dir: Path):
    for table_name in TABLE_NAMES:
        assert (clean_dataset_dir / f"{table_name}.csv").exists(), \
            f"Missing required table: {table_name}.csv"


# ── Row counts ────────────────────────────────────────────────────────────────

def test_sku_count(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "skus.csv")
    assert len(df) == 30, f"Expected 30 SKUs, got {len(df)}"


def test_warehouse_count(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "warehouses.csv")
    assert len(df) == 4, f"Expected 4 warehouses, got {len(df)}"


def test_destination_count(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "destinations.csv")
    assert len(df) == 40, f"Expected 40 destinations, got {len(df)}"


def test_lane_count(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "lanes.csv")
    # 4 warehouses × 40 destinations = 160 lanes
    assert len(df) == 160, f"Expected 160 lanes (4×40), got {len(df)}"


def test_calendar_event_count(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "calendar_events.csv")
    assert len(df) == 420, f"Expected 420 calendar days, got {len(df)}"


def test_config_has_one_row(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "config.csv")
    assert len(df) == 1, f"config.csv must have exactly 1 row, got {len(df)}"


def test_destination_type_split(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "destinations.csv")
    dist = (df["type"] == "distributor").sum()
    stores = (df["type"] == "store").sum()
    assert dist == 10, f"Expected 10 distributors, got {dist}"
    assert stores == 30, f"Expected 30 stores, got {stores}"


# ── Required columns ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_required_columns_present(clean_dataset_dir: Path, table_name: str):
    df = pd.read_csv(clean_dataset_dir / f"{table_name}.csv")
    for col in MANDATORY_COLUMNS[table_name]:
        assert col in df.columns, \
            f"Table '{table_name}' is missing required column '{col}'"


# ── Reproducibility (S2) ─────────────────────────────────────────────────────

def test_same_seed_same_hash(clean_dataset_dir: Path, clean_dataset_dir_seed2: Path, tmp_path: Path):
    """Same seed (42) always produces an identical hash."""
    # Generate a second copy with seed=42
    second_dir = tmp_path / "second_seed42"
    generate_dataset(output_dir=second_dir, seed=42)
    h1 = compute_dataset_hash(clean_dataset_dir)
    h2 = compute_dataset_hash(second_dir)
    assert h1 == h2, "Same seed must produce identical dataset hash (PRD §S2)"


def test_different_seed_different_hash(clean_dataset_dir: Path, clean_dataset_dir_seed2: Path):
    """Seed=42 and seed=99 must produce different datasets."""
    h1 = compute_dataset_hash(clean_dataset_dir)
    h2 = compute_dataset_hash(clean_dataset_dir_seed2)
    assert h1 != h2, "Different seeds must produce different dataset hashes"


def test_hash_stable_across_calls(clean_dataset_dir: Path):
    """compute_dataset_hash must return the same value when called twice on unchanged files."""
    h1 = compute_dataset_hash(clean_dataset_dir)
    h2 = compute_dataset_hash(clean_dataset_dir)
    assert h1 == h2


# ── Primary key uniqueness ────────────────────────────────────────────────────

def test_sku_id_unique(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "skus.csv")
    assert df["sku_id"].is_unique, "skus.sku_id must be unique"


def test_warehouse_id_unique(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "warehouses.csv")
    assert df["warehouse_id"].is_unique


def test_destination_id_unique(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "destinations.csv")
    assert df["dest_id"].is_unique


def test_lane_composite_key_unique(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "lanes.csv")
    assert not df.duplicated(subset=["warehouse_id", "dest_id"]).any(), \
        "lanes (warehouse_id, dest_id) composite key must be unique"


def test_calendar_date_unique(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "calendar_events.csv")
    assert df["date"].is_unique, "calendar_events.date must be unique (PK)"


# ── Foreign key integrity ─────────────────────────────────────────────────────

def test_lanes_warehouse_fk(clean_dataset_dir: Path):
    wh = set(pd.read_csv(clean_dataset_dir / "warehouses.csv")["warehouse_id"])
    lanes = pd.read_csv(clean_dataset_dir / "lanes.csv")
    unknown = set(lanes["warehouse_id"]) - wh
    assert not unknown, f"Lanes reference unknown warehouses: {unknown}"


def test_lanes_dest_fk(clean_dataset_dir: Path):
    dests = set(pd.read_csv(clean_dataset_dir / "destinations.csv")["dest_id"])
    lanes = pd.read_csv(clean_dataset_dir / "lanes.csv")
    unknown = set(lanes["dest_id"]) - dests
    assert not unknown, f"Lanes reference unknown destinations: {unknown}"


def test_sales_sku_fk(clean_dataset_dir: Path):
    skus = set(pd.read_csv(clean_dataset_dir / "skus.csv")["sku_id"])
    sales = pd.read_csv(clean_dataset_dir / "sales_daily.csv")
    unknown = set(sales["sku_id"]) - skus
    assert not unknown, f"sales_daily references unknown SKUs: {unknown}"


def test_sales_dest_fk(clean_dataset_dir: Path):
    dests = set(pd.read_csv(clean_dataset_dir / "destinations.csv")["dest_id"])
    sales = pd.read_csv(clean_dataset_dir / "sales_daily.csv")
    unknown = set(sales["dest_id"]) - dests
    assert not unknown, f"sales_daily references unknown destinations: {unknown}"


# ── No negative quantities ────────────────────────────────────────────────────

def test_no_negative_inventory_quantities(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "inventory_batches.csv")
    assert (df["quantity"] >= 0).all(), "inventory_batches must not have negative quantities"


def test_no_negative_sales(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "sales_daily.csv")
    assert (df["units_sold"] >= 0).all(), "sales_daily must not have negative units_sold"


# ── Valid dates ───────────────────────────────────────────────────────────────

def test_inventory_expiry_dates_parseable(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "inventory_batches.csv")
    parsed = pd.to_datetime(df["expiry_date"], errors="coerce")
    assert parsed.notna().all(), "All inventory_batches.expiry_date must be parseable dates"


def test_sales_dates_parseable(clean_dataset_dir: Path):
    df = pd.read_csv(clean_dataset_dir / "sales_daily.csv")
    parsed = pd.to_datetime(df["date"], errors="coerce")
    assert parsed.notna().all(), "All sales_daily.date must be parseable dates"


# ── Loader ────────────────────────────────────────────────────────────────────

def test_loader_returns_all_tables(clean_dataset_dir: Path):
    dataset, errors = load_dataset(clean_dataset_dir)
    assert dataset is not None, f"Loader failed: {errors}"
    assert errors == [], f"Unexpected loader errors: {errors}"
    d = dataset.as_dict()
    assert set(d.keys()) == set(TABLE_NAMES)
    for name, df in d.items():
        assert isinstance(df, pd.DataFrame), f"{name} should be a DataFrame"
        assert len(df) > 0, f"{name} DataFrame must not be empty"


def test_loader_missing_file_returns_none(tmp_path: Path):
    """Loader with a missing file must return (None, [errors]) not raise."""
    dataset, errors = load_dataset(tmp_path)
    assert dataset is None, "Loader should return None when files are missing"
    assert len(errors) > 0
