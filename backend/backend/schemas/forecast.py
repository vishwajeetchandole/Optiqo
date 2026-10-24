"""
Optiqo — Forecast Schemas
Request and response models for POST /api/forecast (PRD §5.1 P0-04, §10.4).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    """Payload for POST /api/forecast."""

    origin_date: str = Field(
        ...,
        description="ISO-8601 origin date (YYYY-MM-DD). Forecast generates for origin_date+1 .. origin_date+horizon_days.",
        examples=["2024-01-15"],
    )
    horizon_days: int = Field(
        default=7,
        ge=1,
        le=28,
        description="Forecast horizon in days (default 7).",
    )
    use_cache: bool = Field(
        default=True,
        description="If True, return cached forecast if available for the given origin_date and dataset.",
    )
    dataset_path: Optional[str] = Field(
        default=None,
        description="Optional path to dataset directory. Defaults to demo_data/seed_42.",
    )


class ForecastScenarioMultipliers(BaseModel):
    """Empirical scenario multipliers for Low, Mid, and High percentiles."""

    low: float = Field(description="10th percentile empirical residual multiplier.")
    mid: float = Field(description="50th percentile empirical residual multiplier.")
    high: float = Field(description="90th percentile empirical residual multiplier.")


class ForecastScenarios(BaseModel):
    """Cumulative demand values across Low, Mid, and High scenarios."""

    low: float = Field(description="Low scenario demand over horizon.")
    mid: float = Field(description="Mid scenario demand over horizon.")
    high: float = Field(description="High scenario demand over horizon.")


class ForecastItem(BaseModel):
    """Forecast result for a single (destination, SKU) series."""

    sku_id: str = Field(description="SKU identifier.")
    dest_id: str = Field(description="Destination identifier.")
    method: str = Field(description="LIGHTGBM | SEASONAL_NAIVE | MA_28 | FALLBACK_PROFILE")
    is_fallback: bool = Field(default=False, description="True if a fallback rule was triggered.")
    daily_forecast: list[float] = Field(description="Daily forecast values for days 1..horizon.")
    horizon_mean: float = Field(description="Sum of daily forecasts across the horizon.")
    scenario_multipliers: dict[str, float] = Field(description="Low, Mid, High demand multipliers.")
    scenarios: dict[str, float] = Field(description="Low, Mid, High cumulative horizon demands.")


class ForecastSummary(BaseModel):
    """Aggregate statistics for the forecast run."""

    total_series: int = Field(description="Total series forecasted.")
    methods_used: dict[str, int] = Field(description="Count of series by selected method.")
    fallbacks_applied: int = Field(description="Number of series requiring fallback rules.")


class ForecastResponse(BaseModel):
    """Response payload for POST /api/forecast."""

    status: str = Field(description="OK | FALLBACK_FORECAST | ERROR")
    origin_date: str = Field(description="ISO-8601 origin date.")
    horizon_days: int = Field(description="Forecast horizon in days.")
    forecast_summary: ForecastSummary
    forecasts: list[ForecastItem]
