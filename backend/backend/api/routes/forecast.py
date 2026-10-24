"""
Optiqo — Forecast Routes
  POST /api/forecast → Generate multi-step demand forecasts & scenarios (PRD §5.1 P0-04, §10.4)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.core.config import settings
from backend.core.exceptions import DataError, MissingDatasetError
from backend.core.logging import get_logger
from backend.data.loader import load_dataset
from backend.engines.forecasting.adapter import ForecastingAdapter
from backend.engines.protocols import ForecastRequestPayload
from backend.schemas.forecast import (
    ForecastItem,
    ForecastRequest,
    ForecastResponse,
    ForecastSummary,
)

logger = get_logger(__name__)
router = APIRouter()

# In-memory forecast cache: (origin_date, horizon_days, str(data_dir)) -> ForecastResponse
_FORECAST_CACHE: dict[tuple[str, int, str], ForecastResponse] = {}


@router.post(
    "/forecast",
    response_model=ForecastResponse,
    summary="Generate 7-day demand forecasts and scenarios",
    description=(
        "Executes chronological demand forecasting over the specified horizon with strict leakage protection. "
        "Performs automated model selection between LightGBM, Seasonal-Naive, and 28-day Moving Average, "
        "and produces Low, Mid, and High demand scenarios based on validation residuals (PRD §10.4)."
    ),
    tags=["Forecasting"],
)
def generate_demand_forecast(body: ForecastRequest) -> ForecastResponse:
    # 1. Validate origin_date
    try:
        parsed_date = date.fromisoformat(body.origin_date)
    except ValueError:
        raise DataError(
            message=f"Invalid origin_date format: '{body.origin_date}'. Expected ISO-8601 YYYY-MM-DD."
        )

    # 2. Resolve dataset path
    if body.dataset_path:
        data_dir = Path(body.dataset_path)
        if not data_dir.is_absolute():
            data_dir = settings.BASE_DIR / body.dataset_path
    else:
        data_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"

    if not data_dir.exists():
        raise MissingDatasetError(
            message=f"Dataset directory not found: {data_dir}. "
                    "Call GET /api/demo-data first to generate the demo dataset."
        )

    # 3. Check cache
    cache_key = (body.origin_date, body.horizon_days, str(data_dir.resolve()))
    if body.use_cache and cache_key in _FORECAST_CACHE:
        logger.info("Returning cached forecast for key %s", cache_key)
        return _FORECAST_CACHE[cache_key]

    # 4. Load dataset
    ds, errs = load_dataset(data_dir)
    if ds is None or errs:
        raise MissingDatasetError(
            message=f"Could not load dataset from {data_dir}: {'; '.join(errs)}"
        )

    # 5. Invoke Forecaster
    adapter = ForecastingAdapter(seed=settings.DEFAULT_SEED)
    payload = ForecastRequestPayload(
        sales_daily=ds.sales_daily,
        skus=ds.skus,
        calendar_events=ds.calendar_events,
        destinations=ds.destinations,
        origin_date=body.origin_date,
        horizon_days=body.horizon_days,
    )

    output = adapter.generate_forecast(payload)

    # 6. Assemble response
    items: list[ForecastItem] = []
    for _, row in output.forecast_table.iterrows():
        items.append(
            ForecastItem(
                sku_id=str(row["sku_id"]),
                dest_id=str(row["dest_id"]),
                method=str(row["selected_method"]),
                is_fallback=bool(row["is_fallback"]),
                daily_forecast=[float(v) for v in row["daily_forecasts"]],
                horizon_mean=float(row["horizon_mean"]),
                scenario_multipliers={
                    "low": float(row["low_multiplier"]),
                    "mid": float(row["mid_multiplier"]),
                    "high": float(row["high_multiplier"]),
                },
                scenarios={
                    "low": float(row["low_horizon_demand"]),
                    "mid": float(row["mid_horizon_demand"]),
                    "high": float(row["high_horizon_demand"]),
                },
            )
        )

    diag = output.diagnostics
    response = ForecastResponse(
        status=output.status,
        origin_date=body.origin_date,
        horizon_days=body.horizon_days,
        forecast_summary=ForecastSummary(
            total_series=len(items),
            methods_used={str(k): int(v) for k, v in diag.get("methods_count", {}).items()},
            fallbacks_applied=int(diag.get("fallbacks_applied", 0)),
        ),
        forecasts=items,
    )

    if body.use_cache:
        _FORECAST_CACHE[cache_key] = response

    return response
