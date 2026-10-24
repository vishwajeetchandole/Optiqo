"""
Optiqo — 13-Fault Validation Engine (PRD §11.2, P0-02)

Detects all 13 blocking fault types and 3 warning types.
Every finding carries: table, row_index, field, rule, message, observed_value.

Fault types (planning BLOCKED if any present):
  1.  MISSING_FILE                        — required CSV absent
  2.  MISSING_COLUMN                      — mandatory column absent
  3.  MISSING_VALUE                       — NaN / empty in mandatory field
  4.  NON_NUMERIC_OR_NEGATIVE_QUANTITY    — quantity < 0 or non-numeric
  5.  INVALID_DATE                        — unparseable or NaT date in date column
  6.  DUPLICATE_KEY                       — duplicate primary / composite key
  7.  UNKNOWN_SKU                         — foreign-key violation on sku_id
  8.  UNKNOWN_WAREHOUSE                   — foreign-key violation on warehouse_id
  9.  UNKNOWN_DESTINATION                 — foreign-key violation on dest_id
  10. EXPIRED_BATCH                       — batch expiry_date ≤ planning_date
  11. NON_POSITIVE_STORAGE_CAPACITY       — destinations.storage_capacity ≤ 0
  12. NON_POSITIVE_UNIT_VOLUME            — skus.unit_volume ≤ 0
  13. TRANSIT_DAYS_BELOW_ONE             — lanes.transit_days < 1

Warning types (planning allowed):
  W1. SALES_GAP                          — missing date in sales history
  W2. EXTREME_OUTLIER                    — units_sold > 5σ from mean
  W3. STOCK_EXCEEDS_CAPACITY             — destination stock > storage_capacity
"""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.data.loader import (
    MANDATORY_COLUMNS,
    TABLE_NAMES,
    LoadedDataset,
    load_dataset,
)
from backend.schemas.validation import (
    FaultType,
    ValidationFinding,
    WarningType,
)

# Columns treated as quantities (must be numeric and ≥ 0) — fault type 4
QUANTITY_COLUMNS: dict[str, list[str]] = {
    "skus":               ["shelf_life_days", "min_life_days", "unit_volume", "unit_cost", "unit_margin"],
    "inventory_batches":  ["quantity"],
    "inbound_shipments":  ["quantity"],
    "warehouse_receipts": ["quantity"],
    "sales_daily":        ["units_sold"],
}

# Columns that must contain parseable dates — fault type 5
DATE_COLUMNS: dict[str, list[str]] = {
    "sales_daily":         ["date"],
    "inventory_batches":   ["expiry_date"],
    "inbound_shipments":   ["arrival_date", "expiry_date"],
    "warehouse_receipts":  ["arrival_date", "expiry_date"],
    "calendar_events":     ["date"],
}

# Composite / single primary keys per table — fault type 6
PRIMARY_KEYS: dict[str, list[str]] = {
    "skus":               ["sku_id"],
    "warehouses":         ["warehouse_id"],
    "destinations":       ["dest_id"],
    "lanes":              ["warehouse_id", "dest_id"],
    "sales_daily":        ["date", "dest_id", "sku_id"],
    "inventory_batches":  ["location_id", "sku_id", "batch_id"],
    "inbound_shipments":  ["shipment_id"],
    "warehouse_receipts": ["receipt_id"],
    "calendar_events":    ["date"],
}


def validate_dataset(
    data_dir: Path,
    planning_date: Optional[date] = None,
    exclude_expired_batches: bool = True,
) -> tuple[list[ValidationFinding], list[ValidationFinding]]:
    """
    Run the full 13-fault validation engine against the CSVs in data_dir.

    Parameters
    ----------
    data_dir : Path
        Folder containing the 10 CSV tables.
    planning_date : date, optional
        Reference date for expired-batch check (fault 10).  Defaults to today.
    exclude_expired_batches : bool
        If True, expired batches are errors.  If False, they are warnings only.

    Returns
    -------
    (errors, warnings)
        errors  — list[ValidationFinding], planning is BLOCKED if non-empty.
        warnings — list[ValidationFinding], planning is allowed.
    """
    if planning_date is None:
        planning_date = date.today()

    data_dir = Path(data_dir)
    errors: list[ValidationFinding] = []
    warnings: list[ValidationFinding] = []

    # ── Fault 1: Missing required files ──────────────────────────────────────
    missing_files: list[str] = []
    present_files: dict[str, pd.DataFrame] = {}

    for table_name in TABLE_NAMES:
        csv_path = data_dir / f"{table_name}.csv"
        if not csv_path.exists():
            errors.append(_finding(
                table=table_name,
                field=None,
                row_index=None,
                rule=FaultType.MISSING_FILE,
                message=f"Required file '{table_name}.csv' is missing from dataset directory.",
                observed_value=str(csv_path),
            ))
            missing_files.append(table_name)
        else:
            try:
                df = pd.read_csv(csv_path, low_memory=False)
                present_files[table_name] = df
            except Exception as exc:
                errors.append(_finding(
                    table=table_name,
                    field=None,
                    row_index=None,
                    rule=FaultType.MISSING_FILE,
                    message=f"Could not read '{table_name}.csv': {exc}",
                    observed_value=str(csv_path),
                ))
                missing_files.append(table_name)

    # Cannot perform further checks on tables that are absent
    tables = present_files

    # ── Fault 2: Missing required columns ────────────────────────────────────
    tables_with_all_columns: set[str] = set()
    for table_name, df in tables.items():
        missing_cols = [
            col for col in MANDATORY_COLUMNS[table_name]
            if col not in df.columns
        ]
        if missing_cols:
            for col in missing_cols:
                errors.append(_finding(
                    table=table_name,
                    field=col,
                    row_index=None,
                    rule=FaultType.MISSING_COLUMN,
                    message=f"Mandatory column '{col}' is absent from table '{table_name}'.",
                ))
        else:
            tables_with_all_columns.add(table_name)

    # For downstream checks, only use tables that passed column check
    valid_tables = {t: df for t, df in tables.items() if t in tables_with_all_columns}

    # ── Fault 3: Missing required values (NaN / empty in mandatory columns) ──
    for table_name, df in valid_tables.items():
        for col in MANDATORY_COLUMNS[table_name]:
            if col not in df.columns:
                continue
            # Treat empty strings as missing
            col_series = df[col].replace("", np.nan)
            null_mask = col_series.isna()
            for row_idx in df.index[null_mask]:
                errors.append(_finding(
                    table=table_name,
                    field=col,
                    row_index=int(row_idx),
                    rule=FaultType.MISSING_VALUE,
                    message=f"Missing required value in column '{col}' at row {row_idx} of '{table_name}'.",
                ))

    # ── Fault 4: Non-numeric or negative quantities ───────────────────────────
    for table_name, qty_cols in QUANTITY_COLUMNS.items():
        if table_name not in valid_tables:
            continue
        df = valid_tables[table_name]
        for col in qty_cols:
            if col not in df.columns:
                continue
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            # Non-numeric (coerced to NaN but original was not NaN)
            original_not_null = df[col].notna()
            non_numeric_mask = original_not_null & numeric_series.isna()
            for row_idx in df.index[non_numeric_mask]:
                errors.append(_finding(
                    table=table_name, field=col, row_index=int(row_idx),
                    rule=FaultType.NON_NUMERIC_OR_NEGATIVE_QUANTITY,
                    message=f"Non-numeric value in quantity column '{col}' at row {row_idx} of '{table_name}'.",
                    observed_value=str(df.at[row_idx, col]),
                ))
            # Negative
            negative_mask = numeric_series < 0
            for row_idx in df.index[negative_mask]:
                errors.append(_finding(
                    table=table_name, field=col, row_index=int(row_idx),
                    rule=FaultType.NON_NUMERIC_OR_NEGATIVE_QUANTITY,
                    message=f"Negative quantity ({df.at[row_idx, col]}) in column '{col}' at row {row_idx} of '{table_name}'.",
                    observed_value=df.at[row_idx, col],
                ))

    # ── Fault 5: Invalid / unparseable dates ──────────────────────────────────
    for table_name, date_cols in DATE_COLUMNS.items():
        if table_name not in valid_tables:
            continue
        df = valid_tables[table_name]
        for col in date_cols:
            if col not in df.columns:
                continue
            parsed = pd.to_datetime(df[col], errors="coerce")
            # Original non-null but parsed is NaT
            original_not_null = df[col].notna() & (df[col].astype(str).str.strip() != "")
            invalid_mask = original_not_null & parsed.isna()
            for row_idx in df.index[invalid_mask]:
                errors.append(_finding(
                    table=table_name, field=col, row_index=int(row_idx),
                    rule=FaultType.INVALID_DATE,
                    message=f"Unparseable date '{df.at[row_idx, col]}' in column '{col}' at row {row_idx} of '{table_name}'.",
                    observed_value=str(df.at[row_idx, col]),
                ))

    # ── Fault 6: Duplicate primary keys ──────────────────────────────────────
    for table_name, pk_cols in PRIMARY_KEYS.items():
        if table_name not in valid_tables:
            continue
        df = valid_tables[table_name]
        available_pk = [c for c in pk_cols if c in df.columns]
        if len(available_pk) < len(pk_cols):
            continue  # columns missing — already caught in fault 2
        dups = df[df.duplicated(subset=available_pk, keep=False)]
        seen_keys: set = set()
        for row_idx, row in dups.iterrows():
            key_val = tuple(str(row[c]) for c in available_pk)
            if key_val in seen_keys:
                continue
            seen_keys.add(key_val)
            errors.append(_finding(
                table=table_name,
                field=", ".join(available_pk),
                row_index=int(row_idx),
                rule=FaultType.DUPLICATE_KEY,
                message=f"Duplicate primary key {dict(zip(available_pk, key_val))} in table '{table_name}'.",
                observed_value=str(key_val),
            ))

    # ── Build reference sets for FK checks ───────────────────────────────────
    valid_sku_ids: set[str] = set()
    valid_wh_ids: set[str] = set()
    valid_dest_ids: set[str] = set()

    if "skus" in valid_tables:
        valid_sku_ids = set(valid_tables["skus"]["sku_id"].dropna().astype(str))
    if "warehouses" in valid_tables:
        valid_wh_ids = set(valid_tables["warehouses"]["warehouse_id"].dropna().astype(str))
    if "destinations" in valid_tables:
        valid_dest_ids = set(valid_tables["destinations"]["dest_id"].dropna().astype(str))

    # ── Fault 7: Unknown SKU identifier ──────────────────────────────────────
    sku_ref_tables: dict[str, str] = {
        "lanes": None,          # no sku in lanes
        "sales_daily": "sku_id",
        "inventory_batches": "sku_id",
        "inbound_shipments": "sku_id",
        "warehouse_receipts": "sku_id",
    }
    for table_name, col in sku_ref_tables.items():
        if col is None or table_name not in valid_tables or not valid_sku_ids:
            continue
        df = valid_tables[table_name]
        if col not in df.columns:
            continue
        unknown_mask = ~df[col].astype(str).isin(valid_sku_ids) & df[col].notna()
        for row_idx in df.index[unknown_mask]:
            errors.append(_finding(
                table=table_name, field=col, row_index=int(row_idx),
                rule=FaultType.UNKNOWN_SKU,
                message=f"Unknown sku_id '{df.at[row_idx, col]}' at row {row_idx} of '{table_name}'.",
                observed_value=str(df.at[row_idx, col]),
            ))

    # ── Fault 8: Unknown warehouse identifier ─────────────────────────────────
    wh_ref_tables = {
        "lanes": "warehouse_id",
        "warehouse_receipts": "warehouse_id",
        # inventory_batches warehouses checked below via location_type
    }
    for table_name, col in wh_ref_tables.items():
        if table_name not in valid_tables or not valid_wh_ids:
            continue
        df = valid_tables[table_name]
        if col not in df.columns:
            continue
        unknown_mask = ~df[col].astype(str).isin(valid_wh_ids) & df[col].notna()
        for row_idx in df.index[unknown_mask]:
            errors.append(_finding(
                table=table_name, field=col, row_index=int(row_idx),
                rule=FaultType.UNKNOWN_WAREHOUSE,
                message=f"Unknown warehouse_id '{df.at[row_idx, col]}' at row {row_idx} of '{table_name}'.",
                observed_value=str(df.at[row_idx, col]),
            ))

    # inventory_batches: if location_type == 'warehouse', location_id must be a valid warehouse
    if "inventory_batches" in valid_tables and valid_wh_ids:
        df = valid_tables["inventory_batches"]
        if "location_type" in df.columns and "location_id" in df.columns:
            wh_rows = df[df["location_type"].astype(str).str.lower() == "warehouse"]
            unknown_mask = ~wh_rows["location_id"].astype(str).isin(valid_wh_ids)
            for row_idx in wh_rows.index[unknown_mask]:
                errors.append(_finding(
                    table="inventory_batches", field="location_id", row_index=int(row_idx),
                    rule=FaultType.UNKNOWN_WAREHOUSE,
                    message=f"Unknown warehouse location_id '{df.at[row_idx, 'location_id']}' in inventory_batches row {row_idx}.",
                    observed_value=str(df.at[row_idx, "location_id"]),
                ))

    # ── Fault 9: Unknown destination identifier ───────────────────────────────
    dest_ref_tables = {
        "lanes": "dest_id",
        "sales_daily": "dest_id",
        "inbound_shipments": "dest_id",
    }
    for table_name, col in dest_ref_tables.items():
        if table_name not in valid_tables or not valid_dest_ids:
            continue
        df = valid_tables[table_name]
        if col not in df.columns:
            continue
        unknown_mask = ~df[col].astype(str).isin(valid_dest_ids) & df[col].notna()
        for row_idx in df.index[unknown_mask]:
            errors.append(_finding(
                table=table_name, field=col, row_index=int(row_idx),
                rule=FaultType.UNKNOWN_DESTINATION,
                message=f"Unknown dest_id '{df.at[row_idx, col]}' at row {row_idx} of '{table_name}'.",
                observed_value=str(df.at[row_idx, col]),
            ))

    # inventory_batches: location_type == 'destination' → location_id must be valid dest
    if "inventory_batches" in valid_tables and valid_dest_ids:
        df = valid_tables["inventory_batches"]
        if "location_type" in df.columns and "location_id" in df.columns:
            dest_rows = df[df["location_type"].astype(str).str.lower() == "destination"]
            unknown_mask = ~dest_rows["location_id"].astype(str).isin(valid_dest_ids)
            for row_idx in dest_rows.index[unknown_mask]:
                errors.append(_finding(
                    table="inventory_batches", field="location_id", row_index=int(row_idx),
                    rule=FaultType.UNKNOWN_DESTINATION,
                    message=f"Unknown destination location_id '{df.at[row_idx, 'location_id']}' in inventory_batches row {row_idx}.",
                    observed_value=str(df.at[row_idx, "location_id"]),
                ))

    # ── Fault 10: Expired batches ─────────────────────────────────────────────
    batch_tables_with_expiry = ["inventory_batches", "inbound_shipments", "warehouse_receipts"]
    for table_name in batch_tables_with_expiry:
        if table_name not in valid_tables:
            continue
        df = valid_tables[table_name]
        if "expiry_date" not in df.columns:
            continue
        parsed_expiry = pd.to_datetime(df["expiry_date"], errors="coerce")
        plan_dt = pd.Timestamp(planning_date)
        expired_mask = parsed_expiry <= plan_dt
        # Only flag rows where expiry parsed OK (invalid dates already flagged in fault 5)
        expired_and_parseable = expired_mask & parsed_expiry.notna()
        for row_idx in df.index[expired_and_parseable]:
            exp_val = str(df.at[row_idx, "expiry_date"])
            finding_kwargs = dict(
                table=table_name, field="expiry_date", row_index=int(row_idx),
                rule=FaultType.EXPIRED_BATCH,
                message=f"Batch at row {row_idx} in '{table_name}' has expiry_date {exp_val} which is ≤ planning_date {planning_date}.",
                observed_value=exp_val,
            )
            if exclude_expired_batches:
                errors.append(_finding(**finding_kwargs))
            else:
                warnings.append(_finding(**finding_kwargs))

    # ── Fault 11: Non-positive storage capacity (destinations) ────────────────
    if "destinations" in valid_tables:
        df = valid_tables["destinations"]
        if "storage_capacity" in df.columns:
            cap_numeric = pd.to_numeric(df["storage_capacity"], errors="coerce")
            bad_mask = cap_numeric <= 0
            for row_idx in df.index[bad_mask]:
                errors.append(_finding(
                    table="destinations", field="storage_capacity", row_index=int(row_idx),
                    rule=FaultType.NON_POSITIVE_STORAGE_CAPACITY,
                    message=f"storage_capacity must be > 0, got {df.at[row_idx, 'storage_capacity']} at row {row_idx} of 'destinations'.",
                    observed_value=df.at[row_idx, "storage_capacity"],
                ))

    # ── Fault 12: Non-positive unit volume (skus) ─────────────────────────────
    if "skus" in valid_tables:
        df = valid_tables["skus"]
        if "unit_volume" in df.columns:
            vol_numeric = pd.to_numeric(df["unit_volume"], errors="coerce")
            bad_mask = vol_numeric <= 0
            for row_idx in df.index[bad_mask]:
                errors.append(_finding(
                    table="skus", field="unit_volume", row_index=int(row_idx),
                    rule=FaultType.NON_POSITIVE_UNIT_VOLUME,
                    message=f"unit_volume must be > 0, got {df.at[row_idx, 'unit_volume']} at row {row_idx} of 'skus'.",
                    observed_value=df.at[row_idx, "unit_volume"],
                ))

    # ── Fault 13: Transit days below 1 (lanes) ───────────────────────────────
    if "lanes" in valid_tables:
        df = valid_tables["lanes"]
        if "transit_days" in df.columns:
            td_numeric = pd.to_numeric(df["transit_days"], errors="coerce")
            bad_mask = td_numeric < 1
            for row_idx in df.index[bad_mask]:
                errors.append(_finding(
                    table="lanes", field="transit_days", row_index=int(row_idx),
                    rule=FaultType.TRANSIT_DAYS_BELOW_ONE,
                    message=f"transit_days must be ≥ 1, got {df.at[row_idx, 'transit_days']} at row {row_idx} of 'lanes'.",
                    observed_value=df.at[row_idx, "transit_days"],
                ))

    # ── Warning W1: Gaps in sales history ────────────────────────────────────
    if "sales_daily" in valid_tables:
        df = valid_tables["sales_daily"]
        if "date" in df.columns:
            parsed_dates = pd.to_datetime(df["date"], errors="coerce").dropna()
            if len(parsed_dates) > 0:
                date_range = pd.date_range(parsed_dates.min(), parsed_dates.max(), freq="D")
                actual_dates = set(parsed_dates.dt.date)
                for gap_date in date_range:
                    if gap_date.date() not in actual_dates:
                        warnings.append(_finding(
                            table="sales_daily", field="date", row_index=None,
                            rule=WarningType.SALES_GAP,
                            message=f"No sales records found for date {gap_date.date()} — gap in sales history.",
                            observed_value=str(gap_date.date()),
                        ))

    # ── Warning W2: Extreme demand outliers ──────────────────────────────────
    if "sales_daily" in valid_tables:
        df = valid_tables["sales_daily"]
        if "units_sold" in df.columns:
            vals = pd.to_numeric(df["units_sold"], errors="coerce").dropna()
            if len(vals) > 10:
                mean_val = vals.mean()
                std_val = vals.std()
                if std_val > 0:
                    outlier_mask = vals > (mean_val + 5 * std_val)
                    for row_idx in df.index[outlier_mask]:
                        warnings.append(_finding(
                            table="sales_daily", field="units_sold", row_index=int(row_idx),
                            rule=WarningType.EXTREME_OUTLIER,
                            message=f"Extreme outlier units_sold={df.at[row_idx, 'units_sold']:.1f} at row {row_idx} (mean={mean_val:.1f}, σ={std_val:.1f}).",
                            observed_value=df.at[row_idx, "units_sold"],
                        ))

    # ── Warning W3: Destination stock exceeds storage capacity ───────────────
    if "inventory_batches" in valid_tables and "destinations" in valid_tables and "skus" in valid_tables:
        batches = valid_tables["inventory_batches"]
        dests = valid_tables["destinations"]
        skus_df = valid_tables["skus"]

        dest_batches = batches[
            (batches["location_type"].astype(str).str.lower() == "destination") &
            batches["quantity"].notna() &
            batches["location_id"].notna()
        ].copy()

        if len(dest_batches) > 0 and "unit_volume" in skus_df.columns:
            merged = dest_batches.merge(
                skus_df[["sku_id", "unit_volume"]], on="sku_id", how="left"
            )
            merged["volume"] = (
                pd.to_numeric(merged["quantity"], errors="coerce") *
                pd.to_numeric(merged["unit_volume"], errors="coerce")
            )
            total_vol = merged.groupby("location_id")["volume"].sum()
            cap_lookup = dict(zip(
                dests["dest_id"].astype(str),
                pd.to_numeric(dests["storage_capacity"], errors="coerce")
            ))
            for dest_id, vol in total_vol.items():
                cap = cap_lookup.get(str(dest_id))
                if cap and not math.isnan(vol) and vol > cap:
                    warnings.append(_finding(
                        table="inventory_batches", field="quantity", row_index=None,
                        rule=WarningType.STOCK_EXCEEDS_CAPACITY,
                        message=f"Destination '{dest_id}' total stock volume ({vol:.0f}) exceeds storage_capacity ({cap:.0f}).",
                        observed_value={"dest_id": str(dest_id), "total_volume": round(vol, 1), "capacity": cap},
                    ))

    return errors, warnings


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_python(val: Any) -> Any:
    """Convert numpy scalars and pandas objects to native Python types for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {str(k): _to_python(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_python(v) for v in val]
    if isinstance(val, set):
        return [_to_python(v) for v in sorted(val, key=str)]
    if pd.isna(val):
        return None
    if hasattr(val, "item") and callable(getattr(val, "item")):
        try:
            return val.item()
        except Exception:
            pass
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    return val


def _finding(
    table: str,
    field: str | None,
    row_index: int | None,
    rule: FaultType | WarningType,
    message: str,
    observed_value=None,
) -> ValidationFinding:
    return ValidationFinding(
        table=table,
        row_index=int(row_index) if row_index is not None else None,
        field=field,
        rule=rule.value if hasattr(rule, "value") else str(rule),
        message=message,
        observed_value=_to_python(observed_value),
    )

