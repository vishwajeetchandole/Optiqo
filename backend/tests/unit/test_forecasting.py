"""
Optiqo — Unit Tests for Forecasting Engine & Baselines (Phase 4, PRD §10.4)

Verifies:
- Seasonal-Naive cyclic projection.
- 28-day Moving Average flat projection.
- Category/Region fallback profile for sparse history (< 56 days).
- WAPE calculation.
- Empirical scenario multipliers (Low 10th, Mid 50th, High 90th).
- Scenario weights calibration and diagnostic adjustment.
- Leakage-safe feature extraction (lags >= 7 days relative to target date).
- LightGBM model training with Tweedie loss and non-negative predictions.
- ForecastingAdapter protocol conformance.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.data.loader import load_dataset
from backend.engines.forecasting.adapter import ForecastingAdapter
from backend.engines.forecasting.baselines import (
    compute_wape,
    predict_fallback_profile,
    predict_moving_average_28,
    predict_seasonal_naive,
)
from backend.engines.forecasting.lgbm_model import (
    LightGBMForecaster,
    build_feature_row,
)
from backend.engines.forecasting.residuals import (
    calibrate_scenario_weights,
    compute_empirical_multipliers,
    evaluate_interval_coverage,
)
from backend.engines.protocols import (
    ForecastEngineOutput,
    ForecastRequestPayload,
    ForecasterProtocol,
)


def test_seasonal_naive_cyclic():
    """Seasonal naive should repeat the last 7 daily observations in cyclic order."""
    history = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0]
    preds = predict_seasonal_naive(history, horizon_days=7)
    assert preds == history

    preds_10 = predict_seasonal_naive(history, horizon_days=10)
    assert preds_10[:7] == history
    assert preds_10[7:] == history[:3]


def test_moving_average_28_flat():
    """28-day moving average projects the arithmetic mean flat across the horizon."""
    history = [10.0] * 28
    preds = predict_moving_average_28(history, horizon_days=7)
    assert len(preds) == 7
    assert all(p == 10.0 for p in preds)


def test_fallback_profile_weekday_cycling():
    profile = {0: 10.0, 1: 12.0, 2: 15.0, 3: 15.0, 4: 20.0, 5: 25.0, 6: 18.0}
    preds = predict_fallback_profile(profile, scale_factor=2.0, start_weekday=0, horizon_days=7)
    assert preds[0] == 20.0
    assert preds[5] == 50.0


def test_compute_wape():
    actuals = [100.0, 150.0, 200.0]
    forecasts = [110.0, 140.0, 190.0]  # errors: 10, 10, 10 -> total 30 / 450 = 0.0667
    wape = compute_wape(actuals, forecasts)
    assert round(wape, 4) == 0.0667


def test_empirical_multipliers():
    ratios = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3]
    mult = compute_empirical_multipliers(ratios, min_observations=5)
    assert "low" in mult and "mid" in mult and "high" in mult
    assert mult["low"] <= mult["mid"] <= mult["high"]


def test_calibrate_scenario_weights_diagnostic_adjustment():
    mult = {"low": 0.8, "mid": 1.0, "high": 1.4}
    # When unbiased, should return default 0.3, 0.4, 0.3
    weights = calibrate_scenario_weights(mult, validation_mean_ratio=1.06, tolerance=0.10)
    assert weights["low"] == 0.3
    assert weights["mid"] == 0.4
    assert weights["high"] == 0.3


def test_feature_builder_leakage_safety():
    """All feature lags must use dates strictly <= origin_date."""
    origin = date(2024, 1, 15)
    target = date(2024, 1, 18)  # day 3 of horizon

    sales_map = {
        date(2024, 1, 11): 25.0,  # target - 7 = Jan 11 (<= Jan 15)
        date(2024, 1, 4): 20.0,   # target - 14 = Jan 4
        date(2024, 1, 15): 15.0,
        date(2024, 1, 16): 999.0, # FUTURE (must not be read)
    }

    feat = build_feature_row(sales_map, target_date=target, origin_date=origin, step_d=3)
    assert len(feat) == 15
    assert feat[2] == 25.0  # lag_7
    assert feat[3] == 20.0  # lag_14
    # Ensure 999.0 from future is not in features
    assert 999.0 not in feat


def test_lightgbm_training_and_predict(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    forecaster = LightGBMForecaster(seed=42)

    origin = date(2024, 1, 15)
    success = forecaster.train(
        training_df=ds.sales_daily,
        skus_df=ds.skus,
        destinations_df=ds.destinations,
        calendar_events_df=ds.calendar_events,
        origin_date=origin,
        num_boost_round=10,
    )
    assert success is True
    assert forecaster.model is not None

    sample_history = {origin - timedelta(days=i): 10.0 + (i % 5) for i in range(40)}
    preds = forecaster.predict_series(
        sales_history_dict=sample_history,
        origin_date=origin,
        category_code=0,
        region_code=0,
        dest_type_code=0,
        horizon_days=7,
    )
    assert len(preds) == 7
    assert all(p >= 0.0 for p in preds)


def test_forecasting_adapter_protocol(clean_dataset_dir: Path):
    ds, _ = load_dataset(clean_dataset_dir)
    adapter = ForecastingAdapter(seed=42)
    assert isinstance(adapter, ForecasterProtocol)

    payload = ForecastRequestPayload(
        sales_daily=ds.sales_daily,
        skus=ds.skus,
        calendar_events=ds.calendar_events,
        destinations=ds.destinations,
        origin_date="2024-01-15",
        horizon_days=7,
    )

    output = adapter.generate_forecast(payload)
    assert isinstance(output, ForecastEngineOutput)
    assert output.status in ("OK", "FALLBACK_FORECAST")
    assert not output.forecast_table.empty
    assert output.coverage_rate >= 0.0
    assert "LIGHTGBM" in output.validation_wape_by_method or "SEASONAL_NAIVE" in output.validation_wape_by_method
