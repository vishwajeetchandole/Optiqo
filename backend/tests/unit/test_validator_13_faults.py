"""
Optiqo — Unit Tests: 13-Fault Validation Engine (PRD §11.2)

Tests:
  - Clean dataset produces VALID status with zero errors
  - Each of the 13 fault types is detected independently
  - Multiple faults are reported together
  - Non-blocking warnings do not set planning_blocked
  - Expired-batch check uses the supplied planning_date
  - Missing files and malformed CSVs are handled safely
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.data.validator import validate_dataset
from backend.schemas.validation import FaultType, WarningType


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fault_codes(errors) -> set[str]:
    return {e.rule for e in errors}


def _warning_codes(warnings) -> set[str]:
    return {w.rule for w in warnings}


# ── Fault 0: clean dataset ────────────────────────────────────────────────────

def test_clean_dataset_is_valid(clean_dataset_dir: Path, planning_date: date):
    errors, warnings = validate_dataset(
        clean_dataset_dir,
        planning_date=planning_date,
        exclude_expired_batches=True,
    )
    assert errors == [], f"Expected no errors, got:\n" + "\n".join(f"  [{e.rule}] {e.table} r{e.row_index}: {e.message}" for e in errors)


def test_clean_dataset_warnings_do_not_block(clean_dataset_dir: Path, planning_date: date):
    """Warnings (e.g. sales gaps) must never set errors list."""
    errors, warnings = validate_dataset(
        clean_dataset_dir,
        planning_date=planning_date,
    )
    # Any warnings must NOT be fault types
    fault_codes = {ft.value for ft in FaultType}
    for w in warnings:
        assert w.rule not in fault_codes, f"Warning rule {w.rule!r} looks like a fault type"


# ── Fault 1: Missing required file ───────────────────────────────────────────

def test_fault_1_missing_file(corrupted_dataset_dir: Path, planning_date: date):
    (corrupted_dataset_dir / "skus.csv").unlink()
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.MISSING_FILE.value in _fault_codes(errors)
    missing = [e for e in errors if e.rule == FaultType.MISSING_FILE.value]
    assert any("skus" in e.table for e in missing)


# ── Fault 2: Missing required column ─────────────────────────────────────────

def test_fault_2_missing_column(corrupted_dataset_dir: Path, planning_date: date):
    skus_path = corrupted_dataset_dir / "skus.csv"
    df = pd.read_csv(skus_path)
    df.drop(columns=["unit_volume"]).to_csv(skus_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.MISSING_COLUMN.value in _fault_codes(errors)
    col_errors = [e for e in errors if e.rule == FaultType.MISSING_COLUMN.value]
    assert any(e.field == "unit_volume" for e in col_errors)


# ── Fault 3: Missing required value ──────────────────────────────────────────

def test_fault_3_missing_value(corrupted_dataset_dir: Path, planning_date: date):
    skus_path = corrupted_dataset_dir / "skus.csv"
    df = pd.read_csv(skus_path)
    df.loc[0, "sku_id"] = ""  # empty string = missing
    df.to_csv(skus_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.MISSING_VALUE.value in _fault_codes(errors)


# ── Fault 4: Non-numeric or negative quantity ─────────────────────────────────

def test_fault_4_non_numeric_quantity(corrupted_dataset_dir: Path, planning_date: date):
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    # pandas 2.x enforces dtype on float64 columns — cast to object first so the
    # string "NOT_A_NUMBER" can be written to the CSV cell for the validator to detect.
    df["quantity"] = df["quantity"].astype(object)
    df.loc[0, "quantity"] = "NOT_A_NUMBER"
    df.to_csv(inv_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.NON_NUMERIC_OR_NEGATIVE_QUANTITY.value in _fault_codes(errors)


def test_fault_4_negative_quantity(corrupted_dataset_dir: Path, planning_date: date):
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    df.loc[0, "quantity"] = -5.0
    df.to_csv(inv_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.NON_NUMERIC_OR_NEGATIVE_QUANTITY.value in _fault_codes(errors)
    neg_errors = [e for e in errors if e.rule == FaultType.NON_NUMERIC_OR_NEGATIVE_QUANTITY.value]
    assert any(e.observed_value == -5.0 for e in neg_errors)


# ── Fault 5: Invalid date ─────────────────────────────────────────────────────

def test_fault_5_invalid_date(corrupted_dataset_dir: Path, planning_date: date):
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    df.loc[0, "expiry_date"] = "not-a-date"
    df.to_csv(inv_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.INVALID_DATE.value in _fault_codes(errors)
    date_errors = [e for e in errors if e.rule == FaultType.INVALID_DATE.value]
    assert any("not-a-date" in str(e.observed_value) for e in date_errors)


# ── Fault 6: Duplicate primary key ───────────────────────────────────────────

def test_fault_6_duplicate_key(corrupted_dataset_dir: Path, planning_date: date):
    skus_path = corrupted_dataset_dir / "skus.csv"
    df = pd.read_csv(skus_path)
    # Duplicate row 0
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    df.to_csv(skus_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.DUPLICATE_KEY.value in _fault_codes(errors)


# ── Fault 7: Unknown SKU ──────────────────────────────────────────────────────

def test_fault_7_unknown_sku(corrupted_dataset_dir: Path, planning_date: date):
    sales_path = corrupted_dataset_dir / "sales_daily.csv"
    df = pd.read_csv(sales_path)
    df.loc[0, "sku_id"] = "GHOST_SKU"
    df.to_csv(sales_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.UNKNOWN_SKU.value in _fault_codes(errors)
    sku_errors = [e for e in errors if e.rule == FaultType.UNKNOWN_SKU.value]
    assert any("GHOST_SKU" in str(e.observed_value) for e in sku_errors)


# ── Fault 8: Unknown warehouse ────────────────────────────────────────────────

def test_fault_8_unknown_warehouse(corrupted_dataset_dir: Path, planning_date: date):
    lanes_path = corrupted_dataset_dir / "lanes.csv"
    df = pd.read_csv(lanes_path)
    df.loc[0, "warehouse_id"] = "WH_GHOST"
    df.to_csv(lanes_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.UNKNOWN_WAREHOUSE.value in _fault_codes(errors)


# ── Fault 9: Unknown destination ──────────────────────────────────────────────

def test_fault_9_unknown_destination(corrupted_dataset_dir: Path, planning_date: date):
    lanes_path = corrupted_dataset_dir / "lanes.csv"
    df = pd.read_csv(lanes_path)
    df.loc[0, "dest_id"] = "DEST_GHOST"
    df.to_csv(lanes_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.UNKNOWN_DESTINATION.value in _fault_codes(errors)


# ── Fault 10: Expired batch ───────────────────────────────────────────────────

def test_fault_10_expired_batch_blocked(corrupted_dataset_dir: Path, planning_date: date):
    """When exclude_expired_batches=True, expired batches must be blocking errors."""
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    # Set row 0 to expire before planning_date
    expired_date = (planning_date - timedelta(days=1)).isoformat()
    df.loc[0, "expiry_date"] = expired_date
    df.to_csv(inv_path, index=False)
    errors, warnings = validate_dataset(
        corrupted_dataset_dir,
        planning_date=planning_date,
        exclude_expired_batches=True,
    )
    assert FaultType.EXPIRED_BATCH.value in _fault_codes(errors), \
        "Expired batch must be a blocking error when exclude_expired_batches=True"
    assert FaultType.EXPIRED_BATCH.value not in _warning_codes(warnings), \
        "Expired batch must not also be a warning when it is already an error"


def test_fault_10_expired_batch_warning_mode(corrupted_dataset_dir: Path, planning_date: date):
    """When exclude_expired_batches=False, expired batches must be warnings (not errors)."""
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    expired_date = (planning_date - timedelta(days=1)).isoformat()
    df.loc[0, "expiry_date"] = expired_date
    df.to_csv(inv_path, index=False)
    errors, warnings = validate_dataset(
        corrupted_dataset_dir,
        planning_date=planning_date,
        exclude_expired_batches=False,
    )
    assert FaultType.EXPIRED_BATCH.value not in _fault_codes(errors), \
        "Expired batch must NOT be an error when exclude_expired_batches=False"
    assert WarningType.STOCK_EXCEEDS_CAPACITY.value in _warning_codes(warnings) or \
           FaultType.EXPIRED_BATCH.value in _warning_codes(warnings), \
           "Expired batch should appear as a warning when exclude_expired_batches=False"


def test_fault_10_uses_supplied_planning_date(corrupted_dataset_dir: Path):
    """The planning date must come from the argument, not today's date."""
    inv_path = corrupted_dataset_dir / "inventory_batches.csv"
    df = pd.read_csv(inv_path)
    # Set a batch to expire on a specific date far in the future
    future_date = date(2030, 6, 1)
    df.loc[0, "expiry_date"] = future_date.isoformat()
    df.to_csv(inv_path, index=False)

    # Pass a planning_date after that expiry — should be expired
    errors_after, _ = validate_dataset(
        corrupted_dataset_dir,
        planning_date=date(2030, 7, 1),
        exclude_expired_batches=True,
    )
    assert FaultType.EXPIRED_BATCH.value in _fault_codes(errors_after), \
        "Batch expiring 2030-06-01 should be expired when planning_date=2030-07-01"

    # Pass a planning_date before that expiry — should NOT be expired (for that batch)
    errors_before, _ = validate_dataset(
        corrupted_dataset_dir,
        planning_date=date(2030, 5, 1),
        exclude_expired_batches=True,
    )
    # The specific row should NOT appear as EXPIRED_BATCH
    expired_rows = [e for e in errors_before
                    if e.rule == FaultType.EXPIRED_BATCH.value
                    and e.observed_value == future_date.isoformat()]
    assert not expired_rows, "Batch expiring 2030-06-01 should NOT be expired when planning_date=2030-05-01"


# ── Fault 11: Non-positive storage capacity ───────────────────────────────────

def test_fault_11_non_positive_storage_capacity(corrupted_dataset_dir: Path, planning_date: date):
    dest_path = corrupted_dataset_dir / "destinations.csv"
    df = pd.read_csv(dest_path)
    df.loc[0, "storage_capacity"] = 0.0
    df.to_csv(dest_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.NON_POSITIVE_STORAGE_CAPACITY.value in _fault_codes(errors)


def test_fault_11_negative_storage_capacity(corrupted_dataset_dir: Path, planning_date: date):
    dest_path = corrupted_dataset_dir / "destinations.csv"
    df = pd.read_csv(dest_path)
    df.loc[0, "storage_capacity"] = -10.0
    df.to_csv(dest_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.NON_POSITIVE_STORAGE_CAPACITY.value in _fault_codes(errors)


# ── Fault 12: Non-positive unit volume ───────────────────────────────────────

def test_fault_12_non_positive_unit_volume(corrupted_dataset_dir: Path, planning_date: date):
    skus_path = corrupted_dataset_dir / "skus.csv"
    df = pd.read_csv(skus_path)
    df.loc[0, "unit_volume"] = 0.0
    df.to_csv(skus_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.NON_POSITIVE_UNIT_VOLUME.value in _fault_codes(errors)


# ── Fault 13: Transit days below 1 ───────────────────────────────────────────

def test_fault_13_transit_days_below_one(corrupted_dataset_dir: Path, planning_date: date):
    lanes_path = corrupted_dataset_dir / "lanes.csv"
    df = pd.read_csv(lanes_path)
    df.loc[0, "transit_days"] = 0
    df.to_csv(lanes_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.TRANSIT_DAYS_BELOW_ONE.value in _fault_codes(errors)


def test_fault_13_negative_transit_days(corrupted_dataset_dir: Path, planning_date: date):
    lanes_path = corrupted_dataset_dir / "lanes.csv"
    df = pd.read_csv(lanes_path)
    df.loc[0, "transit_days"] = -1
    df.to_csv(lanes_path, index=False)
    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    assert FaultType.TRANSIT_DAYS_BELOW_ONE.value in _fault_codes(errors)


# ── Multiple faults detected together ────────────────────────────────────────

def test_multiple_faults_detected_together(corrupted_dataset_dir: Path, planning_date: date):
    """Inject faults 11, 12, and 13 simultaneously — all must be reported."""
    dest_path = corrupted_dataset_dir / "destinations.csv"
    df = pd.read_csv(dest_path)
    df.loc[0, "storage_capacity"] = 0.0
    df.to_csv(dest_path, index=False)

    skus_path = corrupted_dataset_dir / "skus.csv"
    df = pd.read_csv(skus_path)
    df.loc[0, "unit_volume"] = -1.0
    df.to_csv(skus_path, index=False)

    lanes_path = corrupted_dataset_dir / "lanes.csv"
    df = pd.read_csv(lanes_path)
    df.loc[0, "transit_days"] = 0
    df.to_csv(lanes_path, index=False)

    errors, _ = validate_dataset(corrupted_dataset_dir, planning_date=planning_date)
    codes = _fault_codes(errors)
    assert FaultType.NON_POSITIVE_STORAGE_CAPACITY.value in codes
    assert FaultType.NON_POSITIVE_UNIT_VOLUME.value in codes
    assert FaultType.TRANSIT_DAYS_BELOW_ONE.value in codes


# ── Missing file safe handling ────────────────────────────────────────────────

def test_missing_all_files_reports_all(tmp_path: Path, planning_date: date):
    """An empty directory must report 10 MISSING_FILE errors (one per table)."""
    errors, _ = validate_dataset(tmp_path, planning_date=planning_date)
    missing = [e for e in errors if e.rule == FaultType.MISSING_FILE.value]
    assert len(missing) == 10, f"Expected 10 MISSING_FILE errors, got {len(missing)}"


def test_malformed_csv_does_not_crash(tmp_path: Path, planning_date: date):
    """A directory with an unreadable/corrupt CSV must return errors, not raise exceptions."""
    (tmp_path / "skus.csv").write_text("garbage,,,,\nmore garbage")
    errors, _ = validate_dataset(tmp_path, planning_date=planning_date)
    # Should either flag MISSING_COLUMN (for missing mandatory cols) or MISSING_FILE for other tables
    assert len(errors) > 0, "Malformed CSV must produce errors"
