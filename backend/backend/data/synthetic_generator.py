"""
Optiqo — Deterministic Synthetic FMCG Dataset Generator (PRD §11.3)

Generates a self-consistent, reproducibly seeded CSV dataset with:
  • 4 warehouses
  • 40 destinations (10 distributors + 30 stores, 4 regions)
  • 30 SKUs in 5 categories
  • 420 days of daily sales history
  • Batch-level warehouse inventory with expiry dates
  • Destination starting inventory (3-10 days of cover)
  • Lanes with distance, transit days, and freight rates
  • Inbound shipments and warehouse receipts for the evaluation window
  • Calendar events (festivals, promotions)
  • Planning config

All generation rules follow PRD §11.3. The same seed always produces
byte-identical CSVs (S2 requirement).
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
import numpy as np
import pandas as pd

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants (PRD §11.3) ─────────────────────────────────────────────────────
N_WAREHOUSES = 4
N_DESTINATIONS = 40  # 10 distributors + 30 stores
N_SKUS = 30
N_DAYS = 420
N_CATEGORIES = 5
REGIONS = ["North", "South", "East", "West"]
CATEGORIES = ["Beverages", "Snacks", "Dairy", "Personal Care", "Household"]

# Shelf lives in days by category (PRD: 10–365 days)
CATEGORY_SHELF_LIVES = {
    "Beverages": 180,
    "Snacks": 90,
    "Dairy": 21,
    "Personal Care": 365,
    "Household": 270,
}

# Base demand rates per category (units/day at base destination)
CATEGORY_BASE_DEMAND = {
    "Beverages": 15.0,
    "Snacks": 12.0,
    "Dairy": 20.0,
    "Personal Care": 6.0,
    "Household": 4.0,
}

# Regional demand factors
REGION_FACTORS = {"North": 1.0, "South": 1.15, "East": 0.90, "West": 1.05}

# Weekday demand multipliers (Mon=0..Sun=6) by category
WEEKDAY_PROFILES = {
    "Beverages": [0.85, 0.90, 0.95, 1.00, 1.20, 1.40, 1.30],
    "Snacks":    [0.80, 0.85, 0.90, 1.00, 1.30, 1.50, 1.35],
    "Dairy":     [1.10, 1.05, 1.00, 0.95, 1.05, 1.15, 1.10],
    "Personal Care": [0.95, 0.95, 1.00, 1.00, 1.05, 1.10, 1.00],
    "Household": [0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.05],
}

# Festival uplift and count per year (PRD §11.3)
N_FESTIVALS = 3
FESTIVAL_DURATION = 5        # days each festival window
FESTIVAL_UPLIFT = 1.50       # ×1.5 during festival

# Promotion parameters
N_PROMOTIONS = 12            # random 7-day promotions per year
PROMOTION_DURATION = 7
PROMOTION_UPLIFT = 1.30


def generate_dataset(
    output_dir: Optional[Path] = None,
    seed: int = 42,
) -> Path:
    """
    Generate the full synthetic FMCG dataset and write 10 CSV files.

    Parameters
    ----------
    output_dir : Path, optional
        Directory to write CSVs.  Defaults to settings.demo_data_dir.
    seed : int
        Random seed for full reproducibility.

    Returns
    -------
    Path
        The directory containing the 10 written CSV files.
    """
    out = Path(output_dir) if output_dir else settings.demo_data_dir
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)

    logger.info("Generating synthetic dataset with seed=%d into %s", seed, out)

    # Reference start date = day 1 of the dataset
    start_date = date(2024, 1, 1)

    # ── 1. SKUs ──────────────────────────────────────────────────────────────
    skus = _generate_skus(rng, start_date)
    _write_csv(skus, out / "skus.csv")

    # ── 2. Warehouses ────────────────────────────────────────────────────────
    warehouses = _generate_warehouses(rng)
    _write_csv(warehouses, out / "warehouses.csv")

    # ── 3. Destinations ──────────────────────────────────────────────────────
    destinations = _generate_destinations(rng)
    _write_csv(destinations, out / "destinations.csv")

    # ── 4. Lanes ─────────────────────────────────────────────────────────────
    wh_coords = dict(zip(warehouses["warehouse_id"], zip(warehouses["_x"], warehouses["_y"])))
    dest_coords = dict(zip(destinations["dest_id"], zip(destinations["_x"], destinations["_y"])))
    lanes = _generate_lanes(rng, warehouses, destinations, wh_coords, dest_coords)
    _write_csv(lanes.drop(columns=["_dist_km"]), out / "lanes.csv")

    # ── 5. Calendar Events ───────────────────────────────────────────────────
    calendar = _generate_calendar(py_rng, start_date, N_DAYS)
    _write_csv(calendar, out / "calendar_events.csv")

    # ── 6. Sales Daily ───────────────────────────────────────────────────────
    sales = _generate_sales(rng, skus, destinations, calendar, start_date, N_DAYS)
    _write_csv(sales, out / "sales_daily.csv")

    # ── 7. Inventory Batches (warehouse + destination starting stock) ─────────
    inv = _generate_inventory_batches(rng, skus, warehouses, destinations, sales, start_date, N_DAYS)
    _write_csv(inv, out / "inventory_batches.csv")

    # ── 8. Inbound Shipments ─────────────────────────────────────────────────
    inbound = _generate_inbound_shipments(rng, skus, destinations, lanes, start_date, N_DAYS)
    _write_csv(inbound, out / "inbound_shipments.csv")

    # ── 9. Warehouse Receipts ────────────────────────────────────────────────
    receipts = _generate_warehouse_receipts(rng, skus, warehouses, start_date, N_DAYS)
    _write_csv(receipts, out / "warehouse_receipts.csv")

    # ── 10. Config ───────────────────────────────────────────────────────────
    config = _generate_config()
    _write_csv(config, out / "config.csv")

    logger.info("Dataset generation complete. %d tables written to %s", 10, out)
    return out


# ── Private generation helpers ────────────────────────────────────────────────

def _generate_skus(rng: np.random.Generator, start_date: date) -> pd.DataFrame:
    """Generate 30 SKUs across 5 categories (PRD §11.3)."""
    rows = []
    sku_idx = 0
    for cat in CATEGORIES:
        n_in_cat = N_SKUS // N_CATEGORIES  # 6 per category
        shelf_life = CATEGORY_SHELF_LIVES[cat]
        for j in range(n_in_cat):
            sku_idx += 1
            sku_id = f"SKU_{sku_idx:03d}"
            # Slight shelf-life variation within category (±20%)
            sl = max(10, int(shelf_life * rng.uniform(0.8, 1.2)))
            # min_life_days: max(2, min(ceil(0.35 * shelf_life), 45)) — PRD §11.3
            min_life = max(2, min(math.ceil(0.35 * sl), 45))
            unit_vol = float(round(rng.uniform(0.001, 0.020), 4))  # m³ per unit
            unit_cost = float(round(rng.uniform(5.0, 150.0), 2))
            margin_rate = rng.uniform(0.15, 0.35)
            unit_margin = float(round(unit_cost * margin_rate, 2))
            rows.append({
                "sku_id": sku_id,
                "name": f"{cat} SKU {j+1}",
                "category": cat,
                "shelf_life_days": sl,
                "min_life_days": min_life,
                "unit_volume": unit_vol,
                "unit_cost": unit_cost,
                "unit_margin": unit_margin,
                "case_size": int(rng.choice([6, 12, 24])),
            })
    return pd.DataFrame(rows)


def _generate_warehouses(rng: np.random.Generator) -> pd.DataFrame:
    """Generate 4 warehouses on a coordinate grid (PRD §11.3)."""
    # Place warehouses roughly at cardinal positions on a 100×100 grid
    positions = [(20, 80), (80, 80), (20, 20), (80, 20)]
    rows = []
    for i, (x, y) in enumerate(positions, 1):
        wh_id = f"WH_{i:02d}"
        rows.append({
            "warehouse_id": wh_id,
            "name": f"Warehouse {i} ({REGIONS[i-1]})",
            "region": REGIONS[i - 1],
            "capacity": float(round(rng.uniform(5000, 15000), 0)),
            "_x": x + rng.uniform(-5, 5),
            "_y": y + rng.uniform(-5, 5),
        })
    return pd.DataFrame(rows)


def _generate_destinations(rng: np.random.Generator) -> pd.DataFrame:
    """Generate exactly N_DESTINATIONS=40 destinations: 10 distributors + 30 stores (PRD §11.3)."""
    rows = []
    dest_idx = 0

    # ── 10 distributors: North=2, South=3, East=2, West=3 ────────────────────
    dist_per_region = {"North": 2, "South": 3, "East": 2, "West": 3}
    for region in REGIONS:
        for _ in range(dist_per_region[region]):
            dest_idx += 1
            size_tier = rng.choice(["Large", "Medium"])
            sf = {"Large": 2.0, "Medium": 1.0}[size_tier]
            rows.append({
                "dest_id": f"DEST_{dest_idx:03d}",
                "name": f"{region} Distributor {dest_idx}",
                "type": "distributor",
                "region": region,
                "storage_capacity": float(round(rng.uniform(500, 2000) * sf, 0)),
                "size_tier": size_tier,
                "_x": rng.uniform(0, 100),
                "_y": rng.uniform(0, 100),
            })

    # ── 30 stores: distribute remainder evenly across regions ─────────────────
    n_stores_needed = N_DESTINATIONS - dest_idx   # = 30
    stores_per_region = n_stores_needed // len(REGIONS)   # = 7
    remainder = n_stores_needed % len(REGIONS)            # = 2  → first 2 regions get 8
    for r_idx, region in enumerate(REGIONS):
        n_stores_this = stores_per_region + (1 if r_idx < remainder else 0)
        for _ in range(n_stores_this):
            dest_idx += 1
            size_tier = rng.choice(["Medium", "Small"])
            sf = {"Medium": 1.0, "Small": 0.5}[size_tier]
            rows.append({
                "dest_id": f"DEST_{dest_idx:03d}",
                "name": f"{region} Store {dest_idx}",
                "type": "store",
                "region": region,
                "storage_capacity": float(round(rng.uniform(100, 800) * sf, 0)),
                "size_tier": size_tier,
                "_x": rng.uniform(0, 100),
                "_y": rng.uniform(0, 100),
            })

    df = pd.DataFrame(rows)
    assert len(df) == N_DESTINATIONS, f"BUG: expected {N_DESTINATIONS} destinations, generated {len(df)}"
    return df


def _generate_lanes(
    rng: np.random.Generator,
    warehouses: pd.DataFrame,
    destinations: pd.DataFrame,
    wh_coords: dict,
    dest_coords: dict,
) -> pd.DataFrame:
    """Generate lanes between all warehouse–destination pairs (PRD §11.3)."""
    rows = []
    for _, wh in warehouses.iterrows():
        wx, wy = wh_coords[wh["warehouse_id"]]
        for _, dest in destinations.iterrows():
            dx, dy = dest_coords[dest["dest_id"]]
            # Straight-line distance × 1.3 (PRD §11.3)
            dist_km = float(round(math.hypot(dx - wx, dy - wy) * 1.3, 1))
            # Transit days 1–3 derived from distance
            transit = int(max(1, min(3, math.ceil(dist_km / 50))))
            # freight_rate: cost per unit-volume per km
            freight_rate = float(round(rng.uniform(0.04, 0.12), 4))
            rows.append({
                "warehouse_id": wh["warehouse_id"],
                "dest_id": dest["dest_id"],
                "distance_km": dist_km,
                "transit_days": transit,
                "freight_rate": freight_rate,
                "blocked": False,
                "_dist_km": dist_km,
            })
    return pd.DataFrame(rows)


def _generate_calendar(
    py_rng: random.Random, start_date: date, n_days: int
) -> pd.DataFrame:
    """Generate 420 days of calendar events with 3 festivals and 12 promotions (PRD §11.3)."""
    rows = []
    all_dates = [start_date + timedelta(days=i) for i in range(n_days)]

    # Place 3 festival windows per year
    year_days = 365
    festival_starts: set[int] = set()
    for _ in range(N_FESTIVALS):
        s = py_rng.randint(0, year_days - FESTIVAL_DURATION)
        festival_starts.add(s)
        # Second year
        festival_starts.add(s + year_days)

    festival_days: set[int] = set()
    for fs in festival_starts:
        for d in range(FESTIVAL_DURATION):
            festival_days.add(fs + d)

    # Random promotions
    promo_days: set[int] = set()
    for _ in range(N_PROMOTIONS):
        s = py_rng.randint(0, n_days - PROMOTION_DURATION)
        for d in range(PROMOTION_DURATION):
            promo_days.add(s + d)

    for i, dt in enumerate(all_dates):
        rows.append({
            "date": dt.isoformat(),
            "festival_flag": i in festival_days,
            "promotion_flag": i in promo_days,
            "weather_index": None,
        })
    return pd.DataFrame(rows)


def _generate_sales(
    rng: np.random.Generator,
    skus: pd.DataFrame,
    destinations: pd.DataFrame,
    calendar: pd.DataFrame,
    start_date: date,
    n_days: int,
) -> pd.DataFrame:
    """
    Generate 420 days × 30 SKUs × 40 destinations of daily sales (PRD §11.3).
    Uses negative-binomial noise with weekday profile, festival/promo uplift,
    regional factors, and destination size factors.
    """
    cal_lookup = {
        row["date"]: row for _, row in calendar.iterrows()
    }
    sku_lookup = {row["sku_id"]: row for _, row in skus.iterrows()}
    dest_lookup = {row["dest_id"]: row for _, row in destinations.iterrows()}

    size_factors = {"Large": 3.0, "Medium": 1.5, "Small": 0.7}

    records = []
    for d_idx in range(n_days):
        dt = start_date + timedelta(days=d_idx)
        dt_str = dt.isoformat()
        cal_row = cal_lookup[dt_str]
        wkday = dt.weekday()

        for _, dest in destinations.iterrows():
            dest_id = dest["dest_id"]
            region = dest["region"]
            sf = size_factors.get(dest["size_tier"], 1.0)
            rf = REGION_FACTORS.get(region, 1.0)

            for _, sku in skus.iterrows():
                sku_id = sku["sku_id"]
                cat = sku["category"]

                base = CATEGORY_BASE_DEMAND[cat]
                weekday_mult = WEEKDAY_PROFILES[cat][wkday]
                # Slow annual cycle (±10%) + mild trend
                annual = 1.0 + 0.10 * math.sin(2 * math.pi * d_idx / 365)
                trend = 1.0 + 0.0002 * d_idx

                mean_demand = base * sf * rf * weekday_mult * annual * trend

                # Event uplift
                if cal_row["festival_flag"]:
                    mean_demand *= FESTIVAL_UPLIFT
                if cal_row["promotion_flag"]:
                    mean_demand *= PROMOTION_UPLIFT

                # Negative-binomial noise: slower SKUs are more intermittent
                # n, p parameterization: mean = n*(1-p)/p
                if mean_demand < 0.5:
                    # Intermittent: mostly zeros
                    units = float(rng.poisson(max(mean_demand, 0)))
                else:
                    # NB with dispersion
                    r_param = max(0.5, mean_demand / 2.0)
                    p_param = r_param / (r_param + mean_demand)
                    units = float(rng.negative_binomial(r_param, p_param))

                if units > 0:
                    records.append({
                        "date": dt_str,
                        "dest_id": dest_id,
                        "sku_id": sku_id,
                        "units_sold": units,
                        "price": float(round(sku["unit_cost"] * (1 + float(rng.uniform(0.05, 0.30))), 2)),
                        "promo_flag": bool(cal_row["promotion_flag"]),
                    })

    return pd.DataFrame(records)


def _generate_inventory_batches(
    rng: np.random.Generator,
    skus: pd.DataFrame,
    warehouses: pd.DataFrame,
    destinations: pd.DataFrame,
    sales: pd.DataFrame,
    start_date: date,
    n_days: int,
) -> pd.DataFrame:
    """
    Generate warehouse inventory batches and destination starting stock (PRD §11.3).
    Warehouse supply designed to cover 97–105% of expected demand across window.
    Destination starting stock at 3–10 days of cover.
    """
    eval_start = n_days - 56       # day 365 in 0-indexed
    eval_end = n_days              # day 420
    eval_start_date = start_date + timedelta(days=eval_start)

    # Pre-compute mean daily demand per (dest_id, sku_id) during eval window
    sales_eval = sales[
        (sales["date"] >= eval_start_date.isoformat())
    ].groupby(["dest_id", "sku_id"])["units_sold"].mean().reset_index()
    sales_eval.columns = ["dest_id", "sku_id", "mean_daily"]

    sku_lookup = {row["sku_id"]: row for _, row in skus.iterrows()}
    dest_ids = list(destinations["dest_id"])
    wh_ids = list(warehouses["warehouse_id"])

    rows = []
    batch_counter = 0

    # ── Warehouse batches ──
    total_dest_demand = {}  # (sku_id) -> total expected eval demand
    for _, row in sales_eval.iterrows():
        sid = row["sku_id"]
        total_dest_demand[sid] = total_dest_demand.get(sid, 0) + row["mean_daily"] * 56

    for _, sku in skus.iterrows():
        sku_id = sku["sku_id"]
        sl = sku["shelf_life_days"]
        network_demand = total_dest_demand.get(sku_id, 100.0)
        # Total supply per warehouse: cover_ratio = 97–105%, split evenly
        cover_ratio = float(rng.uniform(0.97, 1.05))
        total_supply = network_demand * cover_ratio
        per_wh = total_supply / len(wh_ids)

        for wh_id in wh_ids:
            # 2–4 batches per warehouse per SKU, with different expiry dates
            n_batches = int(rng.integers(2, 5))
            remaining = per_wh
            for b_idx in range(n_batches):
                batch_counter += 1
                batch_id = f"B_{batch_counter:06d}"
                qty = remaining if b_idx == n_batches - 1 else float(rng.uniform(0.2, 0.6) * per_wh)
                qty = max(1.0, round(qty))
                remaining -= qty

                # Expiry dates staggered within shelf life (future from eval_start_date)
                days_until_expiry = int(rng.integers(
                    max(7, int(sl * 0.3)),
                    max(8, int(sl * 1.0))
                ))
                expiry = eval_start_date + timedelta(days=days_until_expiry)

                rows.append({
                    "location_id": wh_id,
                    "sku_id": sku_id,
                    "batch_id": batch_id,
                    "location_type": "warehouse",
                    "quantity": qty,
                    "expiry_date": expiry.isoformat(),
                    "received_date": (eval_start_date - timedelta(days=int(rng.integers(1, 30)))).isoformat(),
                })

    # ── Destination starting stock (3–10 days of cover) ──
    for _, dest in destinations.iterrows():
        dest_id = dest["dest_id"]
        for _, sku in skus.iterrows():
            sku_id = sku["sku_id"]
            sl = sku["shelf_life_days"]
            demand_row = sales_eval[
                (sales_eval["dest_id"] == dest_id) & (sales_eval["sku_id"] == sku_id)
            ]
            if demand_row.empty or demand_row["mean_daily"].iloc[0] < 0.01:
                continue
            mean_daily = demand_row["mean_daily"].iloc[0]
            cover_days = float(rng.uniform(3, 10))
            qty = max(1.0, round(mean_daily * cover_days))

            batch_counter += 1
            batch_id = f"DB_{batch_counter:06d}"
            days_until_expiry = int(rng.integers(
                max(7, int(sl * 0.3)),
                max(8, int(sl * 0.9))
            ))
            expiry = eval_start_date + timedelta(days=days_until_expiry)

            rows.append({
                "location_id": dest_id,
                "sku_id": sku_id,
                "batch_id": batch_id,
                "location_type": "destination",
                "quantity": qty,
                "expiry_date": expiry.isoformat(),
                "received_date": (eval_start_date - timedelta(days=int(rng.integers(1, 10)))).isoformat(),
            })

    return pd.DataFrame(rows)


def _generate_inbound_shipments(
    rng: np.random.Generator,
    skus: pd.DataFrame,
    destinations: pd.DataFrame,
    lanes: pd.DataFrame,
    start_date: date,
    n_days: int,
) -> pd.DataFrame:
    """Generate inbound shipments already in transit at the start of eval window."""
    eval_start_date = start_date + timedelta(days=n_days - 56)
    rows = []
    shipment_counter = 0

    # Small number of in-transit shipments per destination-SKU pair
    for _, dest in destinations.iterrows():
        dest_id = dest["dest_id"]
        for _, sku in skus.iterrows():
            if rng.random() > 0.15:  # 15% of pairs have an inbound shipment
                continue
            sku_id = sku["sku_id"]
            sl = sku["shelf_life_days"]
            transit = int(rng.integers(1, 4))
            arrival = eval_start_date + timedelta(days=transit)
            expiry_days = int(rng.integers(
                max(transit + 7, int(sl * 0.3)),
                max(transit + 8, int(sl * 0.9))
            ))
            expiry = eval_start_date + timedelta(days=expiry_days)
            qty = max(1.0, round(float(rng.uniform(10, 100))))

            shipment_counter += 1
            rows.append({
                "shipment_id": f"SHP_{shipment_counter:06d}",
                "dest_id": dest_id,
                "sku_id": sku_id,
                "batch_id": f"ISPH_{shipment_counter:06d}",
                "quantity": qty,
                "arrival_date": arrival.isoformat(),
                "expiry_date": expiry.isoformat(),
            })

    return pd.DataFrame(rows)


def _generate_warehouse_receipts(
    rng: np.random.Generator,
    skus: pd.DataFrame,
    warehouses: pd.DataFrame,
    start_date: date,
    n_days: int,
) -> pd.DataFrame:
    """
    Generate warehouse replenishment receipts for the evaluation window.
    Receipts are identical across all policies (PRD §10.8, §11.5).
    """
    eval_start_date = start_date + timedelta(days=n_days - 56)
    rows = []
    receipt_counter = 0

    # 2 weekly replenishment cycles during the eval window
    for week in range(8):
        receipt_date = eval_start_date + timedelta(days=week * 7 + 3)  # mid-cycle
        for _, wh in warehouses.iterrows():
            wh_id = wh["warehouse_id"]
            for _, sku in skus.iterrows():
                sku_id = sku["sku_id"]
                sl = sku["shelf_life_days"]
                if rng.random() > 0.5:  # not every SKU gets replenished every week
                    continue
                qty = max(1.0, round(float(rng.uniform(20, 200))))
                expiry_days = int(rng.integers(
                    max(14, int(sl * 0.6)),
                    max(15, sl + 1)
                ))
                expiry = receipt_date + timedelta(days=expiry_days)
                receipt_counter += 1
                rows.append({
                    "receipt_id": f"RCP_{receipt_counter:06d}",
                    "warehouse_id": wh_id,
                    "sku_id": sku_id,
                    "batch_id": f"RBTCH_{receipt_counter:06d}",
                    "quantity": qty,
                    "arrival_date": receipt_date.isoformat(),
                    "expiry_date": expiry.isoformat(),
                })

    return pd.DataFrame(rows)


def _generate_config() -> pd.DataFrame:
    """Generate the singleton planning configuration (PRD §11.1, §11.3)."""
    return pd.DataFrame([{
        "shortage_penalty_factor": 1.5,
        "holding_cost_rate": 0.02,
        "horizon": 7,
        "baseline_safety_days": 2,
        "scenario_weight_low": 0.3,
        "scenario_weight_mid": 0.4,
        "scenario_weight_high": 0.3,
    }])


# ── Utility ───────────────────────────────────────────────────────────────────

def _write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV, dropping internal helper columns (prefixed _)."""
    cols_to_drop = [c for c in df.columns if c.startswith("_")]
    df.drop(columns=cols_to_drop).to_csv(path, index=False)
    logger.debug("Wrote %d rows to %s", len(df), path.name)


def compute_dataset_hash(data_dir: Path) -> str:
    """
    Return a SHA-256 hex digest over the sorted contents of all CSV files
    in data_dir.  Identical inputs always produce the same hash (S2).
    """
    h = hashlib.sha256()
    for csv_file in sorted(data_dir.glob("*.csv")):
        h.update(csv_file.name.encode())
        h.update(csv_file.read_bytes())
    return h.hexdigest()
