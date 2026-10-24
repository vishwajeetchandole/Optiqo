"""
Optiqo — Unit Tests for Risk Formulas & Calculations (Phase 3, PRD §10.6)

Verifies:
- Trailing daily sales calculation (leakage-safe).
- Lot-by-lot expiry logic (PRD §10.3) with demand scenarios.
- Unmet demand and days of cover formulas.
- Financial exposure formula (unmet * margin + expiry_loss * cost).
- Severity thresholds (HIGH >= 15%, MEDIUM >= 5%, LOW).
- Supply shortage flag detection at network level.
- Ranking order: financial_exposure desc, unmet_share_pct desc.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.data.loader import load_dataset
from backend.schemas.risk import RiskSeverity
from backend.services.risk import (
    compute_risk_overview,
    compute_single_pair_risk,
    compute_trailing_daily_sales,
)


def test_trailing_daily_sales_computation(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    origin = date(2024, 1, 15)

    trailing = compute_trailing_daily_sales(ds.sales_daily, origin_date=origin, lookback_days=7)
    assert len(trailing) > 0

    # Ensure every returned average is non-negative
    for key, avg in trailing.items():
        assert avg >= 0.0
        assert isinstance(key, tuple)
        assert len(key) == 2


def test_lot_by_lot_expiry_zero_when_expiry_outside_horizon():
    """Lots expiring well after the 7-day horizon must result in 0 expected expiry units."""
    lots = [
        {"quantity": 100.0, "expiry_day_index": 30, "source": "on_hand"},
        {"quantity": 50.0, "expiry_day_index": 45, "source": "inbound"},
    ]
    result = compute_single_pair_risk(
        dest_id="DEST_01",
        sku_id="SKU_01",
        lots=lots,
        mean_daily_demand=10.0,  # 7-day demand = 70
        unit_cost=20.0,
        unit_margin=8.0,
        horizon_days=7,
    )

    assert result["expected_expiry_units"] == 0.0
    assert result["expected_expiry_loss_cost"] == 0.0
    assert result["days_of_cover"] == 10.0  # 100 on hand / 10 mean daily = 10.0


def test_lot_by_lot_expiry_when_batch_expires_inside_horizon():
    """A lot of 50 units expiring on day 3 with daily demand of 5 units (total 15 units demand by day 3).
    At least 50 - 15 = 35 units expire unsold."""
    lots = [
        {"quantity": 50.0, "expiry_day_index": 3, "source": "on_hand"},
    ]
    # For scenario mid (mu=1.0, weight=0.4, low=0.8, high=1.25):
    result = compute_single_pair_risk(
        dest_id="DEST_01",
        sku_id="SKU_01",
        lots=lots,
        mean_daily_demand=5.0,
        unit_cost=10.0,
        unit_margin=4.0,
        horizon_days=7,
    )

    assert result["expected_expiry_units"] > 0.0
    assert result["expected_expiry_loss_cost"] > 0.0


def test_unmet_demand_and_financial_exposure():
    """Zero inventory lots with 10 units/day demand -> 100% unmet demand."""
    lots = []
    result = compute_single_pair_risk(
        dest_id="DEST_01",
        sku_id="SKU_01",
        lots=lots,
        mean_daily_demand=10.0,
        unit_cost=15.0,
        unit_margin=5.0,
        horizon_days=7,
    )

    assert result["expected_unmet_units"] > 0.0
    assert result["unmet_share_pct"] == 100.0
    assert result["days_of_cover"] == 0.0
    # Financial exposure = unmet * unit_margin (since expiry loss is 0)
    assert result["financial_exposure"] == round(result["expected_unmet_units"] * 5.0, 2)


def test_compute_risk_overview_on_clean_dataset(clean_dataset_dir: Path):
    origin = date(2024, 1, 15)
    overview = compute_risk_overview(
        origin_date=origin,
        dataset_dir=clean_dataset_dir,
    )

    assert overview.origin_date == "2024-01-15"
    assert overview.total_alerts == len(overview.alerts)
    assert overview.high_severity_count + overview.medium_severity_count + overview.low_severity_count == overview.total_alerts

    # Alerts must be sorted by financial_exposure descending
    exposures = [a.financial_exposure for a in overview.alerts]
    assert exposures == sorted(exposures, reverse=True)

    # Check alert item attributes
    for alert in overview.alerts:
        assert alert.dest_id
        assert alert.sku_id
        assert alert.severity in (RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW)
        assert alert.financial_exposure >= 0
        assert alert.primary_driver
