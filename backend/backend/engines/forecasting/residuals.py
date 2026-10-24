"""
Optiqo — Forecasting Residuals, Empirical Multipliers & Scenario Weights (PRD §10.4)

Implements:
- Calculation of empirical Low (10th), Mid (50th), and High (90th) percentile multipliers.
- Scenario weight calibration: default (0.3, 0.4, 0.3) with outer-weight diagnostic adjustment
  if bias > 5% (0.15 <= p <= 0.35).
- Coverage rate evaluation (F5 metric).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# Default standard multipliers if insufficient validation history exists
FALLBACK_MULTIPLIERS: dict[str, float] = {
    "low": 0.80,
    "mid": 1.00,
    "high": 1.25,
}

# Default scenario weights
DEFAULT_WEIGHTS: dict[str, float] = {
    "low": 0.30,
    "mid": 0.40,
    "high": 0.30,
}


def compute_empirical_multipliers(
    ratios: list[float] | np.ndarray | pd.Series,
    min_observations: int = 10,
) -> dict[str, float]:
    """
    Compute empirical 10th, 50th, and 90th percentile ratios of actual / forecast.
    """
    clean_ratios = [
        float(r) for r in ratios
        if r is not None and not np.isnan(r) and not np.isinf(r) and r >= 0
    ]

    if len(clean_ratios) < min_observations:
        return FALLBACK_MULTIPLIERS.copy()

    low_p = float(np.percentile(clean_ratios, 10))
    mid_p = float(np.percentile(clean_ratios, 50))
    high_p = float(np.percentile(clean_ratios, 90))

    # Guard against degenerate / inverted quantiles
    low_p = max(0.1, round(low_p, 2))
    mid_p = max(low_p, round(mid_p, 2))
    high_p = max(mid_p, round(high_p, 2))

    return {
        "low": low_p,
        "mid": mid_p,
        "high": high_p,
    }


def calibrate_scenario_weights(
    multipliers: dict[str, float],
    validation_mean_ratio: float = 1.0,
    tolerance: float = 0.05,
) -> dict[str, float]:
    """
    Outer-weight diagnostic adjustment (PRD §10.4 item 4).
    Default pi = (0.3, 0.4, 0.3).
    If weighted mean differs from validation mean ratio by > 5%, adjust outer weight p:
      weighted_mean = p * low + (1 - 2p) * mid + p * high = mid + p * (low + high - 2*mid)
      Solve for p subject to 0.15 <= p <= 0.35.
    """
    mu_low = multipliers["low"]
    mu_mid = multipliers["mid"]
    mu_high = multipliers["high"]

    default_mean = 0.3 * mu_low + 0.4 * mu_mid + 0.3 * mu_high
    bias = abs(default_mean - validation_mean_ratio) / max(0.01, validation_mean_ratio)

    if bias <= tolerance:
        return DEFAULT_WEIGHTS.copy()

    # Solve for p: p * (low + high - 2 * mid) = target - mid
    spread = (mu_low + mu_high - 2.0 * mu_mid)
    if abs(spread) < 1e-5:
        return DEFAULT_WEIGHTS.copy()

    target_p = (validation_mean_ratio - mu_mid) / spread
    p = max(0.15, min(0.35, target_p))

    return {
        "low": round(p, 3),
        "mid": round(1.0 - 2.0 * p, 3),
        "high": round(p, 3),
    }


def evaluate_interval_coverage(
    actuals: list[float] | np.ndarray,
    low_bounds: list[float] | np.ndarray,
    high_bounds: list[float] | np.ndarray,
) -> float:
    """
    F5 metric: fraction of actual 7-day demands falling between low and high scenario bounds.
    """
    act = np.asarray(actuals, dtype=float)
    lb = np.asarray(low_bounds, dtype=float)
    hb = np.asarray(high_bounds, dtype=float)

    if len(act) == 0:
        return 0.80  # Default nominal coverage

    covered = (act >= lb) & (act <= hb)
    return round(float(np.mean(covered)), 4)
