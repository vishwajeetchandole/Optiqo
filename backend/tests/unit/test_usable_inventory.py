"""
Optiqo — Unit Tests for Usable Inventory & Shelf-Life Calculation (Phase 3)

Verifies:
- Arrival date computation (t_arr = t_0 + tau).
- Remaining shelf life computation (r = e - t_arr).
- Batch eligibility rule (C2 hard constraint).
- Partitioning of warehouse inventory into Usable and Unusable subsets.
- Usable + Unusable == Total on-hand warehouse inventory invariant.
- Destination available lot aggregation (on-hand + inbound).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.data.loader import load_dataset
from backend.services.inventory import (
    compute_arrival_date,
    compute_remaining_shelf_life,
    filter_eligible_lane_batches,
    get_destination_lots,
    get_inventory_summary,
    is_batch_eligible,
    partition_warehouse_stock,
)


def test_compute_arrival_date():
    origin = date(2024, 1, 15)
    assert compute_arrival_date(origin, 1) == date(2024, 1, 16)
    assert compute_arrival_date(origin, 3) == date(2024, 1, 18)


def test_compute_remaining_shelf_life():
    arrival = date(2024, 1, 18)
    expiry_valid = date(2024, 3, 1)
    expiry_past = date(2024, 1, 10)

    assert compute_remaining_shelf_life(expiry_valid, arrival) == 43
    assert compute_remaining_shelf_life(expiry_past, arrival) == -8


def test_is_batch_eligible():
    # Eligible: remaining >= min_life (25), not blocked, quantity > 0
    assert is_batch_eligible(remaining_life_at_arrival=30, min_life_days=25, quantity=100.0) is True

    # Ineligible: remaining < min_life
    assert is_batch_eligible(remaining_life_at_arrival=20, min_life_days=25, quantity=100.0) is False

    # Ineligible: blocked lane
    assert is_batch_eligible(remaining_life_at_arrival=30, min_life_days=25, quantity=100.0, blocked=True) is False

    # Ineligible: non-positive quantity
    assert is_batch_eligible(remaining_life_at_arrival=30, min_life_days=25, quantity=0.0) is False
    assert is_batch_eligible(remaining_life_at_arrival=30, min_life_days=25, quantity=-5.0) is False


def test_filter_eligible_lane_batches(clean_dataset_dir: Path):
    ds, errs = load_dataset(clean_dataset_dir)
    assert ds is not None
    assert not errs

    origin = date(2024, 1, 15)
    pairs = filter_eligible_lane_batches(origin, ds.inventory_batches, ds.lanes, ds.skus)

    assert not pairs.empty
    expected_cols = [
        "warehouse_id", "dest_id", "batch_id", "sku_id", "quantity",
        "arrival_date", "remaining_life_at_arrival", "is_eligible",
    ]
    for col in expected_cols:
        assert col in pairs.columns

    # Every eligible pair must satisfy the condition
    eligible_pairs = pairs[pairs["is_eligible"]]
    for _, row in eligible_pairs.iterrows():
        assert row["remaining_life_at_arrival"] >= row["min_life_days"]
        assert row["quantity"] > 0


def test_partition_warehouse_stock_invariant(clean_dataset_dir: Path):
    """Usable warehouse stock + Unusable warehouse stock must exactly equal Total warehouse stock."""
    ds, errs = load_dataset(clean_dataset_dir)
    assert ds is not None

    origin = date(2024, 1, 15)
    wh_batches = ds.inventory_batches[
        ds.inventory_batches["location_type"].astype(str).str.lower() == "warehouse"
    ]
    total_wh_qty = pd.to_numeric(wh_batches["quantity"], errors="coerce").fillna(0).sum()

    usable_df, unusable_df = partition_warehouse_stock(origin, ds.inventory_batches, ds.lanes, ds.skus)

    usable_qty = pd.to_numeric(usable_df["quantity"], errors="coerce").fillna(0).sum()
    unusable_qty = pd.to_numeric(unusable_df["quantity"], errors="coerce").fillna(0).sum()

    assert round(usable_qty + unusable_qty, 2) == round(total_wh_qty, 2)
    assert len(usable_df) + len(unusable_df) == len(wh_batches)


def test_partition_warehouse_stock_identifies_expired_batches(corrupted_dataset_dir: Path):
    """An injected expired batch must be classified into the Unusable partition."""
    ds, _ = load_dataset(corrupted_dataset_dir)
    inv = ds.inventory_batches.copy()

    # Find the first warehouse batch and set expiry_date in the past
    origin = date(2024, 1, 15)
    wh_indices = inv[inv["location_type"].astype(str).str.lower() == "warehouse"].index
    target_idx = wh_indices[0]
    inv.loc[target_idx, "expiry_date"] = "2024-01-01"

    usable_df, unusable_df = partition_warehouse_stock(origin, inv, ds.lanes, ds.skus)

    expired_batch_id = inv.loc[target_idx, "batch_id"]
    unusable_batch_ids = set(unusable_df["batch_id"].astype(str))
    usable_batch_ids = set(usable_df["batch_id"].astype(str))

    assert str(expired_batch_id) in unusable_batch_ids
    assert str(expired_batch_id) not in usable_batch_ids


def test_get_destination_lots_compiles_on_hand_and_inbound(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    origin = date(2024, 1, 15)

    lots_df = get_destination_lots(
        origin_date=origin,
        horizon_days=7,
        batches_df=ds.inventory_batches,
        inbound_df=ds.inbound_shipments,
    )

    assert not lots_df.empty
    assert "source" in lots_df.columns
    assert set(lots_df["source"]).issubset({"on_hand", "inbound"})

    # Check that every lot has expiry_date > arrival_date
    for _, lot in lots_df.iterrows():
        assert lot["expiry_date"] > lot["arrival_date"]
        assert lot["quantity"] > 0


def test_inventory_summary(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    origin = date(2024, 1, 15)

    summary = get_inventory_summary(origin, ds.inventory_batches, ds.lanes, ds.skus)

    assert summary.total_warehouse_stock > 0
    assert summary.total_destination_stock > 0
    assert round(summary.usable_warehouse_stock + summary.unusable_warehouse_stock, 2) == round(summary.total_warehouse_stock, 2)
    assert round(summary.usable_destination_stock + summary.unusable_destination_stock, 2) == round(summary.total_destination_stock, 2)
