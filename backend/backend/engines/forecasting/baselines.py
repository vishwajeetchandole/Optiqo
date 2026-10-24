"""
Optiqo — Forecasting Baseline Models (PRD §5.1 P0-04, §10.4)

Provides:
- Seasonal-Naive: 7-day cyclical persistence from the previous week.
- 28-day Moving Average: Flat horizon projection of recent mean daily demand.
- Category/Region Weekday Profile: Fallback for series with sparse history (< 56 days).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def predict_seasonal_naive(
    sales_history: pd.Series | list[float],
    horizon_days: int = 7,
) -> list[float]:
    """
    Seasonal-Naive baseline (PRD §10.4).
    Repeats the last 7 daily sales observations in order.
    If fewer than 7 observations exist, repeats available observations or defaults to 0.
    """
    if isinstance(sales_history, pd.Series):
        vals = [float(v) for v in sales_history.dropna().tolist()]
    else:
        vals = [float(v) for v in sales_history if v is not None and not np.isnan(v)]

    if not vals:
        return [0.0] * horizon_days

    # Take the last 7 days (or whatever is available)
    last_week = vals[-7:] if len(vals) >= 7 else vals

    # Cycle pattern across horizon
    preds = []
    for d in range(horizon_days):
        val = last_week[d % len(last_week)]
        preds.append(max(0.0, round(float(val), 2)))

    return preds


def predict_moving_average_28(
    sales_history: pd.Series | list[float],
    horizon_days: int = 7,
) -> list[float]:
    """
    28-day Moving Average baseline (PRD §10.4).
    Projects the arithmetic mean of the last 28 days flatly across the horizon.
    """
    if isinstance(sales_history, pd.Series):
        vals = [float(v) for v in sales_history.dropna().tolist()]
    else:
        vals = [float(v) for v in sales_history if v is not None and not np.isnan(v)]

    if not vals:
        return [0.0] * horizon_days

    last_28 = vals[-28:] if len(vals) >= 28 else vals
    mean_val = max(0.0, float(np.mean(last_28)))
    return [round(mean_val, 2)] * horizon_days


def predict_fallback_profile(
    weekday_profile: dict[int, float],
    scale_factor: float = 1.0,
    start_weekday: int = 0,
    horizon_days: int = 7,
) -> list[float]:
    """
    Category/region weekday profile fallback for short history (< 56 days) (PRD §10.4).
    start_weekday is the weekday of day t_0 + 1 (0=Monday, 6=Sunday).
    """
    preds = []
    for d in range(horizon_days):
        wd = (start_weekday + d) % 7
        base_demand = weekday_profile.get(wd, 1.0)
        demand = max(0.0, round(float(base_demand * scale_factor), 2))
        preds.append(demand)
    return preds


def compute_wape(actuals: np.ndarray | list[float], forecasts: np.ndarray | list[float]) -> float:
    """
    Weighted Absolute Percentage Error (WAPE): sum(|y - y_hat|) / sum(y).
    Returns 0.0 if actuals sum to 0.
    """
    act = np.asarray(actuals, dtype=float)
    fc = np.asarray(forecasts, dtype=float)

    total_actual = float(np.sum(act))
    if total_actual <= 0:
        return 0.0 if float(np.sum(np.abs(fc))) == 0 else 1.0

    total_error = float(np.sum(np.abs(act - fc)))
    return round(total_error / total_actual, 4)
