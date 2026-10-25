"""
Optiqo — Inventory Preparation & Shelf-Life Calculation (PRD §5.1 P0-03, §8.2, §10.2)

Provides:
- Exact arrival date and remaining shelf life calculations for warehouse-lane pairs.
- Batch eligibility determination (C2 constraint).
- Partitioning of warehouse stock into Usable and Unusable subsets (ensuring
  Usable + Unusable == Total on-hand).
- Aggregation of destination on-hand and inbound pipeline lots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class InventorySummary:
    """Summary of network inventory usable/unusable breakdown."""

    origin_date: date
    total_warehouse_stock: float
    usable_warehouse_stock: float
    unusable_warehouse_stock: float
    total_destination_stock: float
    usable_destination_stock: float
    unusable_destination_stock: float


def compute_arrival_date(origin_date: date, transit_days: int) -> date:
    """Calculate the shipment arrival date at destination: t_arr = t_0 + tau."""
    return origin_date + timedelta(days=int(transit_days))


def compute_remaining_shelf_life(expiry_date: date, arrival_date: date) -> int:
    """
    Calculate remaining shelf life at arrival (in days): r(b, l) = e_b - t_arr.
    Negative values indicate the batch expires before or on arrival.
    """
    return (expiry_date - arrival_date).days


def is_batch_eligible(
    remaining_life_at_arrival: int,
    min_life_days: int,
    quantity: float,
    blocked: bool = False,
) -> bool:
    """
    Check if a (batch, destination) pair meets Hard Constraint C2:
    - Remaining shelf life at arrival >= SKU min_life_days (m_s)
    - Lane is not blocked
    - Batch has strictly positive quantity (Q_b > 0)
    """
    return (
        remaining_life_at_arrival >= min_life_days
        and not blocked
        and quantity > 0
    )


def filter_eligible_lane_batches(
    origin_date: date,
    batches_df: pd.DataFrame,
    lanes_df: pd.DataFrame,
    skus_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Evaluate every (warehouse_batch, destination) pair across network lanes.

    Returns DataFrame with columns:
      warehouse_id, dest_id, batch_id, sku_id, quantity, expiry_date,
      transit_days, arrival_date, remaining_life_at_arrival, min_life_days,
      is_eligible, freight_rate, distance_km, unit_freight_cost,
      unit_volume, unit_cost, unit_margin
    """
    # 1. Filter warehouse batches
    wh_batches = batches_df[
        batches_df["location_type"].astype(str).str.lower() == "warehouse"
    ].copy()

    if wh_batches.empty:
        return pd.DataFrame()

    # In inventory_batches, warehouse ID is stored in location_id when location_type=='warehouse'
    if "warehouse_id" not in wh_batches.columns and "location_id" in wh_batches.columns:
        wh_batches["warehouse_id"] = wh_batches["location_id"]

    # Drop any pre-existing dest_id column on warehouse batches to prevent collision with lanes_df['dest_id']
    if "dest_id" in wh_batches.columns:
        wh_batches = wh_batches.drop(columns=["dest_id"])

    # Parse expiry dates to datetime.date
    wh_batches["expiry_date_parsed"] = pd.to_datetime(
        wh_batches["expiry_date"], errors="coerce"
    ).dt.date

    # 2. Extract SKU min_life_days and economics
    sku_cols = ["sku_id", "min_life_days", "unit_volume", "unit_cost", "unit_margin"]
    available_sku_cols = [c for c in sku_cols if c in skus_df.columns]
    sku_info = skus_df[available_sku_cols].copy()

    # 3. Merge batches with lanes on warehouse_id
    lane_cols = [
        "warehouse_id",
        "dest_id",
        "distance_km",
        "transit_days",
        "freight_rate",
    ]
    if "blocked" in lanes_df.columns:
        lane_cols.append("blocked")

    pairs = wh_batches.merge(lanes_df[lane_cols], on="warehouse_id", how="inner")
    pairs = pairs.merge(sku_info, on="sku_id", how="left")

    if pairs.empty:
        return pd.DataFrame()

    pairs["unit_freight_cost"] = (
        pairs["freight_rate"] * pairs["distance_km"] * pairs["unit_volume"]
    )

    # 4. Compute arrival dates and remaining shelf life
    transit_series = pd.to_numeric(pairs["transit_days"], errors="coerce").fillna(1).astype(int)
    arrival_dates = [origin_date + timedelta(days=int(td)) for td in transit_series]
    pairs["arrival_date"] = arrival_dates

    # Remaining shelf life = (expiry_date_parsed - arrival_date).days
    remaining_days = []
    for exp, arr in zip(pairs["expiry_date_parsed"], pairs["arrival_date"]):
        if exp is None or pd.isna(exp) or arr is None:
            remaining_days.append(-9999)
        else:
            remaining_days.append((exp - arr).days)
    pairs["remaining_life_at_arrival"] = remaining_days

    # Blocked status
    if "blocked" in pairs.columns:
        is_blocked = pairs["blocked"].fillna(False).astype(bool)
    else:
        is_blocked = pd.Series(False, index=pairs.index)

    # Eligibility evaluation: r >= min_life, not blocked, quantity > 0
    min_life = pd.to_numeric(pairs["min_life_days"], errors="coerce").fillna(0)
    qty = pd.to_numeric(pairs["quantity"], errors="coerce").fillna(0)

    pairs["is_eligible"] = (
        (pairs["remaining_life_at_arrival"] >= min_life)
        & (~is_blocked)
        & (qty > 0)
    )

    return pairs


def partition_warehouse_stock(
    origin_date: date,
    batches_df: pd.DataFrame,
    lanes_df: pd.DataFrame,
    skus_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Partition warehouse inventory into Usable and Unusable subsets (PRD §5.1 P0-03, §10.2).

    A batch is Usable if:
      - quantity > 0
      - expiry_date > origin_date (not already expired)
      - Can reach at least ONE destination with remaining_life_at_arrival >= min_life_days on an unblocked lane.

    A batch is Unusable if:
      - quantity <= 0, OR
      - expiry_date <= origin_date (expired), OR
      - It cannot reach ANY destination before violating the shelf-life requirement (r < m_s for all lanes).

    Guarantees:
      usable_stock + unusable_stock == total_warehouse_stock
    """
    wh_batches = batches_df[
        batches_df["location_type"].astype(str).str.lower() == "warehouse"
    ].copy()

    if wh_batches.empty:
        empty = pd.DataFrame(columns=batches_df.columns)
        return empty, empty

    wh_batches["quantity_clean"] = pd.to_numeric(wh_batches["quantity"], errors="coerce").fillna(0)
    wh_batches["expiry_date_parsed"] = pd.to_datetime(
        wh_batches["expiry_date"], errors="coerce"
    ).dt.date

    # Find all eligible pairs
    pairs = filter_eligible_lane_batches(origin_date, wh_batches, lanes_df, skus_df)

    if not pairs.empty and "is_eligible" in pairs.columns:
        eligible_pairs = pairs[pairs["is_eligible"]]
        usable_keys = set(
            zip(
                eligible_pairs["location_id"].astype(str),
                eligible_pairs["sku_id"].astype(str),
                eligible_pairs["batch_id"].astype(str),
            )
        )
    else:
        usable_keys = set()

    is_usable_mask = [
        (str(row["location_id"]), str(row["sku_id"]), str(row["batch_id"])) in usable_keys
        and row["quantity_clean"] > 0
        and row["expiry_date_parsed"] is not None
        and row["expiry_date_parsed"] > origin_date
        for _, row in wh_batches.iterrows()
    ]

    wh_batches["is_usable"] = is_usable_mask

    usable_df = wh_batches[wh_batches["is_usable"]].drop(
        columns=["quantity_clean", "expiry_date_parsed", "is_usable"], errors="ignore"
    )
    unusable_df = wh_batches[~wh_batches["is_usable"]].drop(
        columns=["quantity_clean", "expiry_date_parsed", "is_usable"], errors="ignore"
    )

    return usable_df, unusable_df


def get_destination_lots(
    origin_date: date,
    horizon_days: int = 7,
    batches_df: Optional[pd.DataFrame] = None,
    inbound_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Compile all destination-available inventory lots: on-hand batches plus
    inbound shipments arriving within the planning horizon (PRD §10.2).

    Returns DataFrame:
      dest_id, sku_id, batch_id, quantity, expiry_date, arrival_date,
      source ('on_hand' | 'inbound'), expiry_day_index (days relative to origin_date)
    """
    lots: list[dict] = []

    # 1. On-hand destination batches
    if batches_df is not None and not batches_df.empty:
        if "location_type" in batches_df.columns:
            dest_batches = batches_df[
                batches_df["location_type"].astype(str).str.lower() == "destination"
            ].copy()
        else:
            dest_batches = pd.DataFrame()

        for _, row in dest_batches.iterrows():
            qty = float(row.get("quantity", 0) or 0)
            if qty <= 0:
                continue
            exp_parsed = pd.to_datetime(row.get("expiry_date"), errors="coerce")
            if pd.isna(exp_parsed):
                continue
            exp_date = exp_parsed.date()
            if exp_date <= origin_date:
                # Expired before/on planning date -> unusable
                continue

            lots.append({
                "dest_id": str(row["location_id"]),
                "sku_id": str(row["sku_id"]),
                "batch_id": str(row["batch_id"]),
                "quantity": qty,
                "expiry_date": exp_date,
                "arrival_date": origin_date,
                "source": "on_hand",
                "expiry_day_index": (exp_date - origin_date).days,
            })

    # 2. Inbound shipments arriving within [origin_date + 1, origin_date + horizon_days]
    if inbound_df is not None and not inbound_df.empty:
        horizon_end = origin_date + timedelta(days=horizon_days)

        for _, row in inbound_df.iterrows():
            qty = float(row.get("quantity", 0) or 0)
            if qty <= 0:
                continue
            arr_parsed = pd.to_datetime(row.get("arrival_date"), errors="coerce")
            exp_parsed = pd.to_datetime(row.get("expiry_date"), errors="coerce")
            if pd.isna(arr_parsed) or pd.isna(exp_parsed):
                continue
            arr_date = arr_parsed.date()
            exp_date = exp_parsed.date()

            # Must arrive within planning horizon and expire after arrival
            if origin_date < arr_date <= horizon_end and exp_date > arr_date:
                lots.append({
                    "dest_id": str(row["dest_id"]),
                    "sku_id": str(row["sku_id"]),
                    "batch_id": str(row.get("batch_id", row.get("shipment_id", ""))),
                    "quantity": qty,
                    "expiry_date": exp_date,
                    "arrival_date": arr_date,
                    "source": "inbound",
                    "expiry_day_index": (exp_date - origin_date).days,
                })

    if not lots:
        return pd.DataFrame(columns=[
            "dest_id", "sku_id", "batch_id", "quantity", "expiry_date",
            "arrival_date", "source", "expiry_day_index"
        ])

    df_lots = pd.DataFrame(lots)
    df_lots.sort_values(by=["dest_id", "sku_id", "expiry_date"], inplace=True)
    df_lots.reset_index(drop=True, inplace=True)
    return df_lots


def get_inventory_summary(
    origin_date: date,
    batches_df: pd.DataFrame,
    lanes_df: pd.DataFrame,
    skus_df: pd.DataFrame,
) -> InventorySummary:
    """Compute overall network inventory summary and usable/unusable breakdown."""
    wh_batches = batches_df[
        batches_df["location_type"].astype(str).str.lower() == "warehouse"
    ].copy()
    dest_batches = batches_df[
        batches_df["location_type"].astype(str).str.lower() == "destination"
    ].copy()

    total_wh = float(pd.to_numeric(wh_batches["quantity"], errors="coerce").fillna(0).sum())
    total_dest = float(pd.to_numeric(dest_batches["quantity"], errors="coerce").fillna(0).sum())

    usable_wh_df, unusable_wh_df = partition_warehouse_stock(
        origin_date, batches_df, lanes_df, skus_df
    )
    usable_wh = float(pd.to_numeric(usable_wh_df["quantity"], errors="coerce").fillna(0).sum())
    unusable_wh = float(pd.to_numeric(unusable_wh_df["quantity"], errors="coerce").fillna(0).sum())

    # Destination usable stock (unexpired)
    dest_batches["expiry_parsed"] = pd.to_datetime(
        dest_batches["expiry_date"], errors="coerce"
    ).dt.date
    dest_qty = pd.to_numeric(dest_batches["quantity"], errors="coerce").fillna(0)
    is_dest_unexpired = [
        exp is not None and exp > origin_date
        for exp in dest_batches["expiry_parsed"]
    ]

    usable_dest = float(dest_qty[is_dest_unexpired].sum())
    unusable_dest = total_dest - usable_dest

    return InventorySummary(
        origin_date=origin_date,
        total_warehouse_stock=total_wh,
        usable_warehouse_stock=usable_wh,
        unusable_warehouse_stock=unusable_wh,
        total_destination_stock=total_dest,
        usable_destination_stock=usable_dest,
        unusable_destination_stock=unusable_dest,
    )
