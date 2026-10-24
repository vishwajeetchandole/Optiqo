"""
Optiqo — LightGBM Demand Forecasting Model (PRD §5.1 P0-04, §10.4)

Implements:
- Leakage-safe feature extraction:
  - Lags of 7, 14, 21, 28 days relative to target date (all lags >= 7 days).
  - Rolling mean and std of 7 and 28 days up to t_0.
  - Target weekday, forecast step d (1..7).
  - Planned festival and promotion flags on the target date.
  - Categorical encodings (category, region, destination type).
- LightGBM regressor training with Tweedie loss (variance power = 1.5).
- Multi-step horizon prediction with zero-clipping.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.core.logging import get_logger

logger = get_logger(__name__)


def build_feature_row(
    sales_history_dict: dict[date, float],
    target_date: date,
    origin_date: date,
    step_d: int,
    category_code: int = 0,
    region_code: int = 0,
    dest_type_code: int = 0,
    festival_flag: int = 0,
    promo_flag: int = 0,
) -> list[float]:
    """
    Construct a single feature vector for predicting target_date from origin_date.
    STRICTLY LEAKAGE-SAFE:
    - All lags are relative to target_date and are >= 7 days (so always <= origin_date).
    - Rolling stats use history strictly <= origin_date.
    """
    # Lags relative to target_date (target_date - 7 <= origin_date for step 1..7)
    lag_7 = sales_history_dict.get(target_date - timedelta(days=7), 0.0)
    lag_14 = sales_history_dict.get(target_date - timedelta(days=14), 0.0)
    lag_21 = sales_history_dict.get(target_date - timedelta(days=21), 0.0)
    lag_28 = sales_history_dict.get(target_date - timedelta(days=28), 0.0)

    # Rolling 7 and 28 days up to origin_date
    history_7 = [sales_history_dict.get(origin_date - timedelta(days=i), 0.0) for i in range(7)]
    history_28 = [sales_history_dict.get(origin_date - timedelta(days=i), 0.0) for i in range(28)]

    mean_7 = float(np.mean(history_7))
    std_7 = float(np.std(history_7))
    mean_28 = float(np.mean(history_28))
    std_28 = float(np.std(history_28))

    weekday = target_date.weekday()

    return [
        float(step_d),
        float(weekday),
        float(lag_7),
        float(lag_14),
        float(lag_21),
        float(lag_28),
        float(mean_7),
        float(std_7),
        float(mean_28),
        float(std_28),
        float(category_code),
        float(region_code),
        float(dest_type_code),
        float(festival_flag),
        float(promo_flag),
    ]


FEATURE_NAMES = [
    "step_d", "weekday", "lag_7", "lag_14", "lag_21", "lag_28",
    "mean_7", "std_7", "mean_28", "std_28",
    "category_code", "region_code", "dest_type_code",
    "festival_flag", "promo_flag",
]


class LightGBMForecaster:
    """
    LightGBM multi-step demand forecaster with Tweedie objective (PRD §10.4).
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.model: Optional[lgb.Booster] = None
        self.trained_categories: set[str] = set()

    def train(
        self,
        training_df: pd.DataFrame,
        skus_df: pd.DataFrame,
        destinations_df: pd.DataFrame,
        calendar_events_df: pd.DataFrame,
        origin_date: date,
        max_samples: int = 10000,
        num_boost_round: int = 40,
    ) -> bool:
        """
        Train LightGBM model on historical observations strictly prior to origin_date.
        """
        try:
            # Map lookups
            sku_cat_map = dict(zip(skus_df["sku_id"].astype(str), skus_df["category"].astype(str)))
            dest_reg_map = dict(zip(destinations_df["dest_id"].astype(str), destinations_df["region"].astype(str)))
            dest_typ_map = dict(zip(destinations_df["dest_id"].astype(str), destinations_df["type"].astype(str)))

            categories = sorted(list(set(sku_cat_map.values())))
            regions = sorted(list(set(dest_reg_map.values())))
            types = sorted(list(set(dest_typ_map.values())))

            cat_to_id = {c: i for i, c in enumerate(categories)}
            reg_to_id = {r: i for i, r in enumerate(regions)}
            typ_to_id = {t: i for i, t in enumerate(types)}

            # Build fast date index for sales
            sales = training_df.copy()
            sales["date_parsed"] = pd.to_datetime(sales["date"], errors="coerce").dt.date
            sales["units_clean"] = pd.to_numeric(sales["units_sold"], errors="coerce").fillna(0)

            # Restrict training strictly to <= origin_date
            sales = sales[sales["date_parsed"] <= origin_date]
            if len(sales) < 100:
                logger.warning("Insufficient sales data to train LightGBM (< 100 rows).")
                return False

            # Calendar events lookup
            cal = calendar_events_df.copy()
            cal["date_parsed"] = pd.to_datetime(cal["date"], errors="coerce").dt.date
            fest_map = dict(zip(cal["date_parsed"], pd.to_numeric(cal["festival_flag"], errors="coerce").fillna(0)))

            # Sample training origins across historical weeks
            min_date = sales["date_parsed"].min() + timedelta(days=35)
            if min_date >= origin_date:
                min_date = origin_date - timedelta(days=14)

            # Build series history map: (dest_id, sku_id) -> dict[date, units]
            series_history: dict[tuple[str, str], dict[date, float]] = {}
            for _, row in sales.iterrows():
                key = (str(row["dest_id"]), str(row["sku_id"]))
                if key not in series_history:
                    series_history[key] = {}
                series_history[key][row["date_parsed"]] = float(row["units_clean"])

            X_rows: list[list[float]] = []
            y_rows: list[float] = []

            # Generate training instances from historical 7-day origin slices
            sample_origins = [
                origin_date - timedelta(days=7 * k)
                for k in range(1, 8)
                if (origin_date - timedelta(days=7 * k)) >= min_date
            ]
            if not sample_origins:
                sample_origins = [origin_date - timedelta(days=7)]

            for hist_origin in sample_origins:
                for key, h_dict in list(series_history.items())[:100]:
                    d_id, s_id = key
                    c_id = cat_to_id.get(sku_cat_map.get(s_id, ""), 0)
                    r_id = reg_to_id.get(dest_reg_map.get(d_id, ""), 0)
                    t_id = typ_to_id.get(dest_typ_map.get(d_id, ""), 0)

                    for step in range(1, 8):
                        t_date = hist_origin + timedelta(days=step)
                        if t_date not in h_dict:
                            continue
                        target_val = h_dict[t_date]
                        feat = build_feature_row(
                            sales_history_dict=h_dict,
                            target_date=t_date,
                            origin_date=hist_origin,
                            step_d=step,
                            category_code=c_id,
                            region_code=r_id,
                            dest_type_code=t_id,
                            festival_flag=int(fest_map.get(t_date, 0)),
                        )
                        X_rows.append(feat)
                        y_rows.append(target_val)
                        if len(X_rows) >= max_samples:
                            break
                    if len(X_rows) >= max_samples:
                        break

            if len(X_rows) < 50:
                logger.warning("Insufficient training pairs generated (%d rows).", len(X_rows))
                return False

            X_train = np.array(X_rows, dtype=np.float32)
            y_train = np.array(y_rows, dtype=np.float32)

            dtrain = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES)
            params = {
                "objective": "tweedie",
                "tweedie_variance_power": 1.5,
                "learning_rate": 0.08,
                "num_leaves": 31,
                "min_child_samples": 5,
                "verbosity": -1,
                "seed": self.seed,
            }
            self.model = lgb.train(params, dtrain, num_boost_round=num_boost_round)
            logger.info("Trained LightGBM model successfully on %d samples.", len(X_rows))
            return True

        except Exception as exc:
            logger.warning("LightGBM training failed: %s", exc)
            self.model = None
            return False

    def predict_series(
        self,
        sales_history_dict: dict[date, float],
        origin_date: date,
        category_code: int = 0,
        region_code: int = 0,
        dest_type_code: int = 0,
        festival_map: Optional[dict[date, int]] = None,
        horizon_days: int = 7,
    ) -> list[float]:
        """
        Generate multi-step horizon forecast for a single series.
        """
        if self.model is None:
            raise RuntimeError("Model has not been trained or failed during training.")

        fest_map = festival_map or {}
        feature_matrix = []

        for step in range(1, horizon_days + 1):
            t_date = origin_date + timedelta(days=step)
            feat = build_feature_row(
                sales_history_dict=sales_history_dict,
                target_date=t_date,
                origin_date=origin_date,
                step_d=step,
                category_code=category_code,
                region_code=region_code,
                dest_type_code=dest_type_code,
                festival_flag=fest_map.get(t_date, 0),
            )
            feature_matrix.append(feat)

        X_pred = np.array(feature_matrix, dtype=np.float32)
        raw_preds = self.model.predict(X_pred)

        # Clip negatives to zero
        clean_preds = [max(0.0, round(float(p), 2)) for p in raw_preds]
        return clean_preds
