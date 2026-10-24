"""
Optiqo — Inventory & Supply Risk Analysis Service (PRD §5.1 P0-07, §10.6)

Implements:
- Destination-SKU lot-by-lot expiry and unmet demand calculation across demand scenarios.
- Days of cover, unmet demand share, expiry loss, excess stock, and financial exposure.
- Network-level supply shortage detection.
- Deterministic severity classification (HIGH, MEDIUM, LOW) and exposure ranking.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.config import settings
from backend.core.exceptions import MissingDatasetError
from backend.core.logging import get_logger
from backend.data.loader import LoadedDataset, load_dataset
from backend.schemas.risk import RiskAlertItem, RiskOverviewResponse, RiskSeverity
from backend.services.inventory import (
    get_destination_lots,
    partition_warehouse_stock,
)

logger = get_logger(__name__)

# Default scenario weights (PRD §10.4)
DEFAULT_SCENARIO_WEIGHTS: dict[str, float] = {
    "low": 0.3,
    "mid": 0.4,
    "high": 0.3,
}

# Default scenario multipliers (PRD §10.4)
DEFAULT_SCENARIO_MULTIPLIERS: dict[str, float] = {
    "low": 0.8,
    "mid": 1.0,
    "high": 1.25,
}


def compute_trailing_daily_sales(
    sales_daily_df: pd.DataFrame,
    origin_date: date,
    lookback_days: int = 7,
) -> dict[tuple[str, str], float]:
    """
    Compute trailing daily average sales for each (dest_id, sku_id) pair
    over the lookback window up to origin_date (leakage-safe).
    """
    if sales_daily_df.empty:
        return {}

    sales = sales_daily_df.copy()
    sales["date_parsed"] = pd.to_datetime(sales["date"], errors="coerce").dt.date
    sales["units_clean"] = pd.to_numeric(sales["units_sold"], errors="coerce").fillna(0)

    start_date = origin_date - timedelta(days=lookback_days - 1)
    window = sales[(sales["date_parsed"] >= start_date) & (sales["date_parsed"] <= origin_date)]

    if window.empty:
        # Fallback to broader 28-day window if available
        start_date_28 = origin_date - timedelta(days=28 - 1)
        window = sales[(sales["date_parsed"] >= start_date_28) & (sales["date_parsed"] <= origin_date)]
        div = 28.0
    else:
        div = float(lookback_days)

    grouped = window.groupby(["dest_id", "sku_id"])["units_clean"].sum()

    trailing_map: dict[tuple[str, str], float] = {}
    for (d_id, s_id), total_units in grouped.items():
        trailing_map[(str(d_id), str(s_id))] = float(total_units) / div

    return trailing_map


def compute_single_pair_risk(
    dest_id: str,
    sku_id: str,
    lots: list[dict],
    mean_daily_demand: float,
    unit_cost: float,
    unit_margin: float,
    horizon_days: int = 7,
    scenario_weights: dict[str, float] | None = None,
    scenario_multipliers: dict[str, float] | None = None,
) -> dict:
    """
    Evaluate risk for a single (dest_id, sku_id) pair using PRD §10.3 lot-by-lot logic.
    """
    weights = scenario_weights or DEFAULT_SCENARIO_WEIGHTS
    multipliers = scenario_multipliers or DEFAULT_SCENARIO_MULTIPLIERS

    # Sort lots by expiry day index (ascending)
    sorted_lots = sorted(lots, key=lambda x: x["expiry_day_index"])
    total_stock = sum(lot["quantity"] for lot in sorted_lots)
    on_hand_stock = sum(lot["quantity"] for lot in sorted_lots if lot.get("source") == "on_hand")

    # Horizon base demand
    base_horizon_demand = mean_daily_demand * horizon_days

    # Calculate days of cover
    if mean_daily_demand > 0:
        days_of_cover = round(on_hand_stock / mean_daily_demand, 1)
    else:
        days_of_cover = 999.0 if on_hand_stock > 0 else 0.0

    scenario_metrics: dict[str, dict[str, float]] = {}

    for k in ["low", "mid", "high"]:
        mu_k = multipliers[k]
        # Cumulative scenario demand by day n: D_k(n) = mu_k * min(n, H) * mean_daily
        # Horizon demand: D_k(H) = mu_k * base_horizon_demand
        horizon_demand_k = mu_k * base_horizon_demand

        # Lot-by-lot expiry logic (PRD §10.3)
        wc = 0.0
        cum_qty = 0.0
        for lot in sorted_lots:
            cum_qty += lot["quantity"]
            n_j = lot["expiry_day_index"]
            if n_j <= horizon_days:
                demand_up_to_n = mu_k * max(0, min(n_j, horizon_days)) * mean_daily_demand
                lot_expired = max(0.0, cum_qty - demand_up_to_n)
                wc = max(wc, lot_expired)

        waste_k = wc
        surviving_stock = max(0.0, total_stock - waste_k)
        short_k = max(0.0, horizon_demand_k - surviving_stock)
        end_k = max(0.0, surviving_stock - horizon_demand_k)

        scenario_metrics[k] = {
            "demand": horizon_demand_k,
            "short": short_k,
            "waste": waste_k,
            "end": end_k,
        }

    # Scenario-weighted expectations
    exp_demand = sum(weights[k] * scenario_metrics[k]["demand"] for k in weights)
    exp_unmet = sum(weights[k] * scenario_metrics[k]["short"] for k in weights)
    exp_expiry = sum(weights[k] * scenario_metrics[k]["waste"] for k in weights)
    exp_end = sum(weights[k] * scenario_metrics[k]["end"] for k in weights)

    # Percentage unmet share
    if exp_demand > 0:
        unmet_share_pct = round((exp_unmet / exp_demand) * 100.0, 1)
    else:
        unmet_share_pct = 0.0

    exp_unmet_rounded = round(exp_unmet, 1)
    exp_expiry_rounded = round(exp_expiry, 1)
    exp_expiry_loss = round(exp_expiry_rounded * unit_cost, 2)
    financial_exposure = round((exp_unmet_rounded * unit_margin) + exp_expiry_loss, 2)

    # Excess units beyond 14 days of cover
    excess_threshold = 14.0 * mean_daily_demand
    excess_units = max(0, int(round(exp_end - excess_threshold)))

    return {
        "dest_id": dest_id,
        "sku_id": sku_id,
        "on_hand_stock": round(on_hand_stock, 1),
        "total_available_stock": round(total_stock, 1),
        "days_of_cover": days_of_cover,
        "expected_demand": round(exp_demand, 1),
        "expected_unmet_units": exp_unmet_rounded,
        "unmet_share_pct": unmet_share_pct,
        "expected_expiry_units": exp_expiry_rounded,
        "expected_expiry_loss_cost": exp_expiry_loss,
        "excess_units": excess_units,
        "financial_exposure": financial_exposure,
    }


def compute_risk_overview(
    origin_date: date | str,
    dataset_dir: Optional[Path] = None,
    loaded_dataset: Optional[LoadedDataset] = None,
    horizon_days: int = settings.DEFAULT_HORIZON_DAYS,
    planned_allocations: Optional[pd.DataFrame] = None,
) -> RiskOverviewResponse:
    """
    Run the full PRD §10.6 risk detection pipeline.

    Parameters
    ----------
    origin_date : date | str
        Planning reference date (t_0).
    dataset_dir : Path, optional
        Path containing the 10 CSV tables. Defaults to settings.demo_data_dir/seed_42.
    loaded_dataset : LoadedDataset, optional
        Pre-loaded dataset if already in memory.
    horizon_days : int
        Planning horizon in days (default 7).
    planned_allocations : pd.DataFrame, optional
        If provided, evaluates post-plan risk including planned shipments.
    """
    if isinstance(origin_date, str):
        origin_date = date.fromisoformat(origin_date)

    # Load dataset if not passed in
    if loaded_dataset is None:
        if dataset_dir is None:
            dataset_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"
        dataset_dir = Path(dataset_dir)
        if not dataset_dir.exists():
            raise MissingDatasetError(
                message=f"Dataset directory not found: {dataset_dir}."
            )
        ds, load_errs = load_dataset(dataset_dir)
        if ds is None or load_errs:
            raise MissingDatasetError(
                message=f"Could not load dataset from {dataset_dir}: {'; '.join(load_errs)}"
            )
    else:
        ds = loaded_dataset

    # 1. Trailing demand per (dest_id, sku_id)
    trailing_sales = compute_trailing_daily_sales(
        ds.sales_daily, origin_date=origin_date, lookback_days=7
    )

    # 2. Extract SKU economics
    sku_lookup: dict[str, dict[str, float]] = {}
    for _, row in ds.skus.iterrows():
        s_id = str(row["sku_id"])
        sku_lookup[s_id] = {
            "unit_cost": float(row.get("unit_cost", 10.0) or 10.0),
            "unit_margin": float(row.get("unit_margin", 5.0) or 5.0),
        }

    # 3. Compile destination lots (on-hand + inbound)
    all_lots_df = get_destination_lots(
        origin_date=origin_date,
        horizon_days=horizon_days,
        batches_df=ds.inventory_batches,
        inbound_df=ds.inbound_shipments,
    )

    # Group lots by (dest_id, sku_id)
    lots_by_dest_sku: dict[tuple[str, str], list[dict]] = {}
    if not all_lots_df.empty:
        for _, row in all_lots_df.iterrows():
            key = (str(row["dest_id"]), str(row["sku_id"]))
            if key not in lots_by_dest_sku:
                lots_by_dest_sku[key] = []
            lots_by_dest_sku[key].append(row.to_dict())

    # 4. Total network usable stock vs. network demand per SKU (Supply Shortage check)
    usable_wh_df, _ = partition_warehouse_stock(
        origin_date, ds.inventory_batches, ds.lanes, ds.skus
    )
    wh_usable_by_sku = (
        usable_wh_df.groupby("sku_id")["quantity"].sum().to_dict()
        if not usable_wh_df.empty else {}
    )

    dest_batches = ds.inventory_batches[
        ds.inventory_batches["location_type"].astype(str).str.lower() == "destination"
    ].copy()
    dest_batches["exp_parsed"] = pd.to_datetime(dest_batches["expiry_date"], errors="coerce").dt.date
    dest_batches["qty_num"] = pd.to_numeric(dest_batches["quantity"], errors="coerce").fillna(0)
    dest_usable = dest_batches[dest_batches["exp_parsed"] > origin_date]
    dest_usable_by_sku = (
        dest_usable.groupby("sku_id")["qty_num"].sum().to_dict()
        if not dest_usable.empty else {}
    )

    all_dests = set(ds.destinations["dest_id"].astype(str))
    all_skus = set(ds.skus["sku_id"].astype(str))

    # Calculate total expected demand per SKU across all destinations
    sku_total_demand: dict[str, float] = {}
    sku_total_usable_stock: dict[str, float] = {}

    for s_id in all_skus:
        total_d = sum(
            trailing_sales.get((d_id, s_id), 0.0) * horizon_days
            for d_id in all_dests
        )
        sku_total_demand[s_id] = total_d
        wh_stock = float(wh_usable_by_sku.get(s_id, 0.0) or 0.0)
        dst_stock = float(dest_usable_by_sku.get(s_id, 0.0) or 0.0)
        sku_total_usable_stock[s_id] = wh_stock + dst_stock

    supply_shortage_skus = [
        s_id for s_id in all_skus
        if sku_total_usable_stock[s_id] < sku_total_demand[s_id] and sku_total_demand[s_id] > 0
    ]

    # 5. Evaluate risk alerts for all active (dest_id, sku_id) pairs
    raw_alerts: list[dict] = []

    for d_id in sorted(all_dests):
        for s_id in sorted(all_skus):
            mean_daily = trailing_sales.get((d_id, s_id), 0.0)
            pair_lots = lots_by_dest_sku.get((d_id, s_id), [])

            # Only evaluate pairs with either demand or existing lots
            if mean_daily == 0.0 and not pair_lots:
                continue

            econ = sku_lookup.get(s_id, {"unit_cost": 10.0, "unit_margin": 5.0})
            risk_data = compute_single_pair_risk(
                dest_id=d_id,
                sku_id=s_id,
                lots=pair_lots,
                mean_daily_demand=mean_daily,
                unit_cost=econ["unit_cost"],
                unit_margin=econ["unit_margin"],
                horizon_days=horizon_days,
            )

            is_supply_short = s_id in supply_shortage_skus
            unmet_share = risk_data["unmet_share_pct"]
            exp_loss = risk_data["expected_expiry_loss_cost"]
            on_hand = risk_data["on_hand_stock"]

            # Severity classification (PRD §10.6)
            # HIGH: unmet share >= 15% OR expiry loss >= 15% of on-hand OR (supply shortage and unmet >= 10%)
            # MEDIUM: unmet share >= 5% OR expiry loss >= 5% of on-hand
            # LOW: otherwise
            expiry_ratio = (risk_data["expected_expiry_units"] / on_hand) if on_hand > 0 else 0.0

            if unmet_share >= 15.0 or expiry_ratio >= 0.15 or (is_supply_short and unmet_share >= 10.0):
                severity = RiskSeverity.HIGH
            elif unmet_share >= 5.0 or expiry_ratio >= 0.05:
                severity = RiskSeverity.MEDIUM
            else:
                severity = RiskSeverity.LOW

            # Formulate human-readable primary driver explanation
            if is_supply_short:
                tot_stk = int(round(sku_total_usable_stock[s_id]))
                tot_dem = int(round(sku_total_demand[s_id]))
                driver = f"Total network usable inventory ({tot_stk}) is below network demand ({tot_dem})."
            elif unmet_share >= 15.0:
                driver = f"High stockout risk with {unmet_share:.1f}% unmet demand share and {risk_data['days_of_cover']:.1f} days of cover."
            elif risk_data["expected_expiry_units"] > 0:
                driver = f"Expiry risk: {risk_data['expected_expiry_units']:.0f} units at risk of expiring unsold within the horizon."
            elif risk_data["days_of_cover"] < horizon_days:
                driver = f"Low inventory cover ({risk_data['days_of_cover']:.1f} days) relative to 7-day demand."
            elif risk_data["excess_units"] > 0:
                driver = f"Overstock risk: {risk_data['excess_units']} excess units beyond 14 days of cover."
            else:
                driver = f"Stable stock position with {risk_data['days_of_cover']:.1f} days of cover."

            risk_data["severity"] = severity
            risk_data["is_supply_shortage"] = is_supply_short
            risk_data["primary_driver"] = driver

            # Filter: include alerts that have financial exposure > 0, or supply shortage,
            # or HIGH/MEDIUM severity, or cover < horizon_days
            if (
                risk_data["financial_exposure"] > 0
                or is_supply_short
                or severity in (RiskSeverity.HIGH, RiskSeverity.MEDIUM)
                or risk_data["days_of_cover"] < horizon_days
            ):
                raw_alerts.append(risk_data)

    # 6. Rank alerts: financial_exposure desc, then unmet_share_pct desc (PRD §10.6)
    raw_alerts.sort(
        key=lambda a: (a["financial_exposure"], a["unmet_share_pct"]),
        reverse=True,
    )

    alert_items = [
        RiskAlertItem(
            dest_id=a["dest_id"],
            sku_id=a["sku_id"],
            severity=a["severity"],
            financial_exposure=a["financial_exposure"],
            days_of_cover=a["days_of_cover"],
            expected_unmet_units=a["expected_unmet_units"],
            unmet_share_pct=a["unmet_share_pct"],
            expected_expiry_units=a["expected_expiry_units"],
            expected_expiry_loss_cost=a["expected_expiry_loss_cost"],
            excess_units=a["excess_units"],
            is_supply_shortage=a["is_supply_shortage"],
            primary_driver=a["primary_driver"],
        )
        for a in raw_alerts
    ]

    high_count = sum(1 for a in alert_items if a.severity == RiskSeverity.HIGH)
    med_count = sum(1 for a in alert_items if a.severity == RiskSeverity.MEDIUM)
    low_count = sum(1 for a in alert_items if a.severity == RiskSeverity.LOW)

    logger.info(
        "Risk analysis for %s complete: %d alerts (HIGH=%d, MED=%d, LOW=%d, supply_shortage_skus=%d)",
        origin_date.isoformat(),
        len(alert_items),
        high_count,
        med_count,
        low_count,
        len(supply_shortage_skus),
    )

    return RiskOverviewResponse(
        origin_date=origin_date.isoformat(),
        total_alerts=len(alert_items),
        high_severity_count=high_count,
        medium_severity_count=med_count,
        low_severity_count=low_count,
        supply_shortage_skus=sorted(supply_shortage_skus),
        alerts=alert_items,
    )
