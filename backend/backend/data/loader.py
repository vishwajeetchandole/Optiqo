"""
Optiqo — CSV Dataset Loader
Reads the 10 CSV tables, coerces types, and returns a typed LoadedDataset namedtuple.
Keeps the loader deliberately thin: no validation logic lives here — that belongs in validator.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Mandatory columns per table (PRD §11.1).
# Optional columns are loaded if present and silently skipped if absent.
MANDATORY_COLUMNS: dict[str, list[str]] = {
    "skus":                ["sku_id", "name", "category", "shelf_life_days", "min_life_days", "unit_volume", "unit_cost", "unit_margin"],
    "warehouses":          ["warehouse_id", "name", "region"],
    "destinations":        ["dest_id", "name", "type", "region", "storage_capacity"],
    "lanes":               ["warehouse_id", "dest_id", "distance_km", "transit_days", "freight_rate"],
    "sales_daily":         ["date", "dest_id", "sku_id", "units_sold"],
    "inventory_batches":   ["location_id", "sku_id", "batch_id", "location_type", "quantity", "expiry_date"],
    "inbound_shipments":   ["shipment_id", "dest_id", "sku_id", "batch_id", "quantity", "arrival_date", "expiry_date"],
    "warehouse_receipts":  ["receipt_id", "warehouse_id", "sku_id", "batch_id", "quantity", "arrival_date", "expiry_date"],
    "calendar_events":     ["date", "festival_flag"],
    "config":              ["shortage_penalty_factor", "holding_cost_rate", "horizon", "baseline_safety_days"],
}

TABLE_NAMES = list(MANDATORY_COLUMNS.keys())


@dataclass
class LoadedDataset:
    """Container for all 10 loaded pandas DataFrames, keyed by table name."""

    skus: pd.DataFrame
    warehouses: pd.DataFrame
    destinations: pd.DataFrame
    lanes: pd.DataFrame
    sales_daily: pd.DataFrame
    inventory_batches: pd.DataFrame
    inbound_shipments: pd.DataFrame
    warehouse_receipts: pd.DataFrame
    calendar_events: pd.DataFrame
    config: pd.DataFrame

    def as_dict(self) -> dict[str, pd.DataFrame]:
        return {
            "skus": self.skus,
            "warehouses": self.warehouses,
            "destinations": self.destinations,
            "lanes": self.lanes,
            "sales_daily": self.sales_daily,
            "inventory_batches": self.inventory_batches,
            "inbound_shipments": self.inbound_shipments,
            "warehouse_receipts": self.warehouse_receipts,
            "calendar_events": self.calendar_events,
            "config": self.config,
        }


def load_dataset(data_dir: Path) -> tuple[LoadedDataset | None, list[str]]:
    """
    Load all 10 CSVs from data_dir and perform minimal type coercion.

    Returns
    -------
    (LoadedDataset | None, errors)
        If a mandatory file is missing, returns (None, [error_message]).
        Otherwise returns (LoadedDataset, []) on full success.
        Type coercion errors are collected but do not prevent loading.
    """
    data_dir = Path(data_dir)
    errors: list[str] = []
    tables: dict[str, pd.DataFrame | None] = {}

    for table_name in TABLE_NAMES:
        csv_path = data_dir / f"{table_name}.csv"
        if not csv_path.exists():
            errors.append(f"Missing required file: {table_name}.csv")
            tables[table_name] = None
            continue
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            tables[table_name] = _coerce_types(table_name, df)
            logger.debug("Loaded %s: %d rows", table_name, len(df))
        except Exception as exc:
            errors.append(f"Failed to read {table_name}.csv: {exc}")
            tables[table_name] = None

    if any(v is None for v in tables.values()):
        return None, errors

    dataset = LoadedDataset(
        skus=tables["skus"],
        warehouses=tables["warehouses"],
        destinations=tables["destinations"],
        lanes=tables["lanes"],
        sales_daily=tables["sales_daily"],
        inventory_batches=tables["inventory_batches"],
        inbound_shipments=tables["inbound_shipments"],
        warehouse_receipts=tables["warehouse_receipts"],
        calendar_events=tables["calendar_events"],
        config=tables["config"],
    )
    return dataset, errors


def _coerce_types(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply minimal, safe type coercion so downstream code gets consistent dtypes.
    Coercion errors are silently tolerated here; the validator.py catches them.
    """
    df = df.copy()

    # Date columns
    date_cols: dict[str, list[str]] = {
        "sales_daily":         ["date"],
        "inventory_batches":   ["expiry_date", "received_date"],
        "inbound_shipments":   ["arrival_date", "expiry_date"],
        "warehouse_receipts":  ["arrival_date", "expiry_date"],
        "calendar_events":     ["date"],
    }
    for col in date_cols.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # Numeric columns that must be non-negative floats
    float_cols: dict[str, list[str]] = {
        "skus":               ["shelf_life_days", "min_life_days", "unit_volume", "unit_cost", "unit_margin"],
        "destinations":       ["storage_capacity"],
        "lanes":              ["distance_km", "transit_days", "freight_rate"],
        "sales_daily":        ["units_sold", "price"],
        "inventory_batches":  ["quantity"],
        "inbound_shipments":  ["quantity"],
        "warehouse_receipts": ["quantity"],
        "config":             ["shortage_penalty_factor", "holding_cost_rate", "horizon", "baseline_safety_days"],
    }
    for col in float_cols.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Boolean columns
    bool_cols: dict[str, list[str]] = {
        "lanes":           ["blocked"],
        "sales_daily":     ["promo_flag"],
        "calendar_events": ["festival_flag", "promotion_flag"],
    }
    for col in bool_cols.get(table_name, []):
        if col in df.columns:
            df[col] = df[col].astype(object).where(df[col].notna(), None)

    return df
