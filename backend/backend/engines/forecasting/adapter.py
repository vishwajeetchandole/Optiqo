"""
Optiqo — Forecasting Engine Adapter (PRD §5.1 P0-04, Plan §5.1)

Implements ForecasterProtocol:
- Coordinates Seasonal-Naive, 28-day Moving Average, and LightGBM models.
- Executes model selection via validation WAPE minimization.
- Enforces the automatic fallback cascade:
  1. Series < 56 days history -> FALLBACK_PROFILE
  2. LightGBM error or higher WAPE -> best baseline
  3. Negative values clipped to 0
- Emits standardized ForecastEngineOutput and scenario tables.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from backend.core.logging import get_logger
from backend.engines.forecasting.baselines import (
    compute_wape,
    predict_fallback_profile,
    predict_moving_average_28,
    predict_seasonal_naive,
)
from backend.engines.forecasting.lgbm_model import LightGBMForecaster
from backend.engines.forecasting.residuals import (
    compute_empirical_multipliers,
    evaluate_interval_coverage,
)
from backend.engines.protocols import (
    ForecastEngineOutput,
    ForecastRequestPayload,
    ForecastRowResult,
    ForecasterProtocol,
)

logger = get_logger(__name__)


class ForecastingAdapter(ForecasterProtocol):
    """Reference implementation of ForecasterProtocol satisfying PRD §10.4."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.lgbm = LightGBMForecaster(seed=seed)

    def generate_forecast(self, payload: ForecastRequestPayload) -> ForecastEngineOutput:
        origin_date = date.fromisoformat(payload.origin_date)
        horizon = payload.horizon_days

        sales = payload.sales_daily.copy()
        sales["date_parsed"] = pd.to_datetime(sales["date"], errors="coerce").dt.date
        sales["units_clean"] = pd.to_numeric(sales["units_sold"], errors="coerce").fillna(0)

        # Leakage control: strictly prior to origin_date
        hist_sales = sales[sales["date_parsed"] <= origin_date]

        # Lookups
        skus_df = payload.skus
        dests_df = payload.destinations
        cal_df = payload.calendar_events

        all_skus = sorted(list(set(skus_df["sku_id"].astype(str))))
        all_dests = sorted(list(set(dests_df["dest_id"].astype(str))))

        sku_cat_map = dict(zip(skus_df["sku_id"].astype(str), skus_df["category"].astype(str)))
        dest_reg_map = dict(zip(dests_df["dest_id"].astype(str), dests_df["region"].astype(str)))
        dest_typ_map = dict(zip(dests_df["dest_id"].astype(str), dests_df["type"].astype(str)))

        categories = sorted(list(set(sku_cat_map.values())))
        regions = sorted(list(set(dest_reg_map.values())))
        types = sorted(list(set(dest_typ_map.values())))

        cat_to_id = {c: i for i, c in enumerate(categories)}
        reg_to_id = {r: i for i, r in enumerate(regions)}
        typ_to_id = {t: i for i, t in enumerate(types)}

        # Build series history map
        series_hist_map: dict[tuple[str, str], dict[date, float]] = {}
        series_length_map: dict[tuple[str, str], int] = {}

        for _, row in hist_sales.iterrows():
            key = (str(row["dest_id"]), str(row["sku_id"]))
            if key not in series_hist_map:
                series_hist_map[key] = {}
            series_hist_map[key][row["date_parsed"]] = float(row["units_clean"])

        for key, h_dict in series_hist_map.items():
            if h_dict:
                min_d = min(h_dict.keys())
                series_length_map[key] = (origin_date - min_d).days + 1
            else:
                series_length_map[key] = 0

        # Calendar events lookup
        cal = cal_df.copy()
        cal["date_parsed"] = pd.to_datetime(cal["date"], errors="coerce").dt.date
        fest_map = dict(zip(cal["date_parsed"], pd.to_numeric(cal["festival_flag"], errors="coerce").fillna(0).astype(int)))

        # Category weekday profiles for fallback
        weekday_profiles: dict[str, dict[int, float]] = {}
        for cat in categories:
            cat_skus = set(skus_df[skus_df["category"].astype(str) == cat]["sku_id"].astype(str))
            cat_sales = hist_sales[hist_sales["sku_id"].astype(str).isin(cat_skus)]
            if not cat_sales.empty:
                cat_sales_copy = cat_sales.copy()
                cat_sales_copy["weekday"] = [d.weekday() for d in cat_sales_copy["date_parsed"]]
                grouped = cat_sales_copy.groupby("weekday")["units_clean"].mean().to_dict()
                weekday_profiles[cat] = grouped
            else:
                weekday_profiles[cat] = {i: 5.0 for i in range(7)}

        # ── 1. Train LightGBM model ──────────────────────────────────────────
        lgbm_available = self.lgbm.train(
            training_df=hist_sales,
            skus_df=skus_df,
            destinations_df=dests_df,
            calendar_events_df=cal_df,
            origin_date=origin_date,
        )

        # ── 2. Validation WAPE evaluation for model selection ────────────────
        # Sample validation week: t_0 - 7 days
        val_origin = origin_date - timedelta(days=7)
        val_wapes: dict[str, list[float]] = {"LIGHTGBM": [], "SEASONAL_NAIVE": [], "MA_28": []}
        val_residuals_ratios: list[float] = []
        val_actuals_list: list[float] = []
        val_low_list: list[float] = []
        val_high_list: list[float] = []

        sample_eval_keys = list(series_hist_map.keys())[:40]

        for key in sample_eval_keys:
            h_dict = series_hist_map.get(key, {})
            # Actual 7 days after val_origin
            val_actuals = [h_dict.get(val_origin + timedelta(days=step), 0.0) for step in range(1, 8)]
            if sum(val_actuals) <= 0:
                continue

            # Historical slice up to val_origin
            sub_dict = {d: v for d, v in h_dict.items() if d <= val_origin}
            sub_series = pd.Series([sub_dict.get(val_origin - timedelta(days=i), 0.0) for i in reversed(range(28))])

            pred_sn = predict_seasonal_naive(sub_series, horizon_days=7)
            pred_ma = predict_moving_average_28(sub_series, horizon_days=7)

            val_wapes["SEASONAL_NAIVE"].append(compute_wape(val_actuals, pred_sn))
            val_wapes["MA_28"].append(compute_wape(val_actuals, pred_ma))

            if lgbm_available:
                try:
                    d_id, s_id = key
                    c_id = cat_to_id.get(sku_cat_map.get(s_id, ""), 0)
                    r_id = reg_to_id.get(dest_reg_map.get(d_id, ""), 0)
                    t_id = typ_to_id.get(dest_typ_map.get(d_id, ""), 0)
                    pred_lgb = self.lgbm.predict_series(
                        sales_history_dict=sub_dict,
                        origin_date=val_origin,
                        category_code=c_id,
                        region_code=r_id,
                        dest_type_code=t_id,
                        festival_map=fest_map,
                        horizon_days=7,
                    )
                    val_wapes["LIGHTGBM"].append(compute_wape(val_actuals, pred_lgb))

                    # Track residual ratio: sum(actual) / sum(forecast)
                    sum_pred = max(0.1, sum(pred_lgb))
                    ratio = sum(val_actuals) / sum_pred
                    val_residuals_ratios.append(ratio)
                    val_actuals_list.append(sum(val_actuals))
                except Exception as exc:
                    logger.warning(
                        "LightGBM validation failed for (%s, %s): %s",
                        key[0],
                        key[1],
                        exc,
                        exc_info=True,
                    )

        # Compute average WAPE per method
        mean_wapes: dict[str, float] = {}
        for method, w_list in val_wapes.items():
            mean_wapes[method] = round(float(np.mean(w_list)), 4) if w_list else 0.50

        # Empirical multipliers
        multipliers = compute_empirical_multipliers(val_residuals_ratios)

        # ── 3. Generate forecasts for all (dest_id, sku_id) series ───────────
        results: list[ForecastRowResult] = []
        start_weekday = (origin_date + timedelta(days=1)).weekday()

        for d_id in all_dests:
            for s_id in all_skus:
                key = (d_id, s_id)
                h_dict = series_hist_map.get(key, {})
                hist_len = series_length_map.get(key, 0)
                cat = sku_cat_map.get(s_id, "")

                # Rule 1: Sparse history (< 56 days) -> FALLBACK_PROFILE
                if hist_len < 56:
                    prof = weekday_profiles.get(cat, {i: 5.0 for i in range(7)})
                    daily_fc = predict_fallback_profile(prof, scale_factor=1.0, start_weekday=start_weekday, horizon_days=horizon)
                    method = "FALLBACK_PROFILE"
                    is_fallback = True

                # Rule 2: Model selection based on validation WAPE
                elif lgbm_available and mean_wapes.get("LIGHTGBM", 1.0) < min(mean_wapes.get("SEASONAL_NAIVE", 1.0), mean_wapes.get("MA_28", 1.0)):
                    try:
                        c_id = cat_to_id.get(cat, 0)
                        r_id = reg_to_id.get(dest_reg_map.get(d_id, ""), 0)
                        t_id = typ_to_id.get(dest_typ_map.get(d_id, ""), 0)
                        daily_fc = self.lgbm.predict_series(
                            sales_history_dict=h_dict,
                            origin_date=origin_date,
                            category_code=c_id,
                            region_code=r_id,
                            dest_type_code=t_id,
                            festival_map=fest_map,
                            horizon_days=horizon,
                        )
                        method = "LIGHTGBM"
                        is_fallback = False
                    except Exception as e:
                        logger.warning("LightGBM prediction failed for (%s, %s): %s; triggering fallback.", d_id, s_id, e)
                        series_vals = [h_dict.get(origin_date - timedelta(days=i), 0.0) for i in reversed(range(28))]
                        daily_fc = predict_seasonal_naive(series_vals, horizon_days=horizon)
                        method = "SEASONAL_NAIVE"
                        is_fallback = True

                # Rule 3: Better baseline chosen
                else:
                    series_vals = [h_dict.get(origin_date - timedelta(days=i), 0.0) for i in reversed(range(28))]
                    if mean_wapes.get("SEASONAL_NAIVE", 1.0) <= mean_wapes.get("MA_28", 1.0):
                        daily_fc = predict_seasonal_naive(series_vals, horizon_days=horizon)
                        method = "SEASONAL_NAIVE"
                    else:
                        daily_fc = predict_moving_average_28(series_vals, horizon_days=horizon)
                        method = "MA_28"
                    is_fallback = False

                # Clip negatives to zero
                daily_fc = [max(0.0, round(float(v), 2)) for v in daily_fc]
                h_mean = round(sum(daily_fc), 2)

                low_d = round(h_mean * multipliers["low"], 2)
                mid_d = round(h_mean * multipliers["mid"], 2)
                high_d = round(h_mean * multipliers["high"], 2)

                results.append(
                    ForecastRowResult(
                        sku_id=s_id,
                        dest_id=d_id,
                        selected_method=method,
                        is_fallback=is_fallback,
                        daily_forecasts=daily_fc,
                        horizon_mean=h_mean,
                        low_multiplier=multipliers["low"],
                        mid_multiplier=multipliers["mid"],
                        high_multiplier=multipliers["high"],
                        low_horizon_demand=low_d,
                        mid_horizon_demand=mid_d,
                        high_horizon_demand=high_d,
                    )
                )

        # Standardized DataFrame representation
        forecast_records = [
            {
                "sku_id": r.sku_id,
                "dest_id": r.dest_id,
                "selected_method": r.selected_method,
                "is_fallback": r.is_fallback,
                "daily_forecasts": r.daily_forecasts,
                "horizon_mean": r.horizon_mean,
                "low_multiplier": r.low_multiplier,
                "mid_multiplier": r.mid_multiplier,
                "high_multiplier": r.high_multiplier,
                "low_horizon_demand": r.low_horizon_demand,
                "mid_horizon_demand": r.mid_horizon_demand,
                "high_horizon_demand": r.high_horizon_demand,
            }
            for r in results
        ]
        forecast_df = pd.DataFrame(forecast_records)

        coverage = evaluate_interval_coverage(
            actuals=val_actuals_list,
            low_bounds=[a * multipliers["low"] for a in val_actuals_list],
            high_bounds=[a * multipliers["high"] for a in val_actuals_list],
        )

        # Method breakdown
        methods_count = forecast_df["selected_method"].value_counts().to_dict()
        fallbacks_count = int(forecast_df["is_fallback"].sum())

        status = "FALLBACK_FORECAST" if fallbacks_count > 0 else "OK"

        logger.info(
            "Forecast complete: %d series, methods=%s, fallbacks=%d, coverage=%.2f",
            len(results), methods_count, fallbacks_count, coverage,
        )

        return ForecastEngineOutput(
            status=status,
            forecast_table=forecast_df,
            validation_wape_by_method=mean_wapes,
            coverage_rate=coverage,
            diagnostics={
                "total_series": len(results),
                "methods_count": methods_count,
                "fallbacks_applied": fallbacks_count,
                "lgbm_trained": lgbm_available,
                "multipliers": multipliers,
            },
        )
