"""Build a map-ready view of the dataset and shipment lines for a stored plan run."""

from __future__ import annotations

from datetime import date
import math
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from backend.core.config import settings
from backend.core.exceptions import DataError, MissingDatasetError
from backend.data.loader import load_dataset
from backend.schemas.network_map import (
    LocationRisk,
    NetworkLocation,
    NetworkMapResponse,
    ShipmentFlow,
)
from backend.schemas.risk import RiskAlertItem
from backend.services.inventory import get_destination_lots, partition_warehouse_stock
from backend.storage.repository import compute_dataset_hash, get_run


def _dataset_for_run(run: dict[str, Any]) -> tuple[Path, str]:
    expected_hash = run.get("dataset_hash")
    candidates: list[Path] = []
    stored_path = run.get("_dataset_path")
    if isinstance(stored_path, str) and stored_path:
        candidates.append(Path(stored_path))
    candidates.extend(sorted(settings.demo_data_dir.glob("seed_*")))

    checked: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in checked:
            continue
        checked.add(resolved)
        if resolved.is_dir() and compute_dataset_hash(resolved) == expected_hash:
            return resolved, expected_hash

    raise MissingDatasetError(
        message=(
            f"The source dataset for run '{run.get('run_id')}' is unavailable or "
            "no longer matches its recorded dataset hash."
        )
    )


def _coordinate(row: pd.Series) -> tuple[float | None, float | None, str]:
    latitude_column = "latitude" if "latitude" in row.index else "lat"
    longitude_column = "longitude" if "longitude" in row.index else "lon"
    has_latitude = latitude_column in row.index
    has_longitude = longitude_column in row.index
    if not has_latitude and not has_longitude:
        return None, None, "missing"
    if not has_latitude or not has_longitude:
        return None, None, "invalid"

    try:
        latitude = float(row[latitude_column])
        longitude = float(row[longitude_column])
    except (TypeError, ValueError):
        return None, None, "invalid"

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None, None, "invalid"
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None, None, "invalid"
    return latitude, longitude, "valid"


def _risk_by_destination(risk_records: Any, run_id: str) -> dict[str, LocationRisk]:
    severity_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    grouped: dict[str, list] = {}
    if risk_records is None:
        return {}
    if not isinstance(risk_records, list):
        raise DataError(message=f"Run '{run_id}' contains invalid pre-plan risk data.")
    try:
        alerts = [RiskAlertItem.model_validate(record) for record in risk_records]
    except (ValidationError, TypeError) as exc:
        raise DataError(
            message=f"Run '{run_id}' contains invalid pre-plan risk data."
        ) from exc
    for alert in alerts:
        grouped.setdefault(alert.dest_id, []).append(alert)

    result: dict[str, LocationRisk] = {}
    for dest_id, alerts in grouped.items():
        level = max(
            (alert.severity.value for alert in alerts),
            key=lambda severity: severity_rank[severity],
        )
        result[dest_id] = LocationRisk(
            level=level,
            alert_count=len(alerts),
            expected_unmet_units=round(
                sum(alert.expected_unmet_units for alert in alerts), 1
            ),
            expected_expiry_units=round(
                sum(alert.expected_expiry_units for alert in alerts), 1
            ),
            minimum_days_of_cover=min(alert.days_of_cover for alert in alerts),
            primary_drivers=list(dict.fromkeys(
                alert.primary_driver for alert in alerts if alert.primary_driver
            ))[:3],
        )
    return result


def get_network_map(run_id: str) -> NetworkMapResponse:
    run = get_run(run_id)
    if run.get("run_type", "PLAN") != "PLAN":
        raise DataError(message=f"Run '{run_id}' is not a distribution plan.")

    dataset_dir, dataset_hash = _dataset_for_run(run)
    dataset, load_errors = load_dataset(dataset_dir)
    if dataset is None or load_errors:
        raise MissingDatasetError(
            message=f"The dataset for run '{run_id}' could not be loaded: {'; '.join(load_errors)}"
        )

    origin_date_value = run.get("origin_date")
    try:
        origin_date = date.fromisoformat(str(origin_date_value))
    except (TypeError, ValueError) as exc:
        raise DataError(
            message=f"Run '{run_id}' does not contain a valid planning date."
        ) from exc

    parameters = run.get("parameters") or {}
    try:
        horizon_days = int(parameters.get("horizon_days", settings.DEFAULT_HORIZON_DAYS))
    except (TypeError, ValueError) as exc:
        raise DataError(message=f"Run '{run_id}' has an invalid planning horizon.") from exc
    if not 1 <= horizon_days <= 28:
        raise DataError(message=f"Run '{run_id}' has an invalid planning horizon.")

    warehouse_stock, _ = partition_warehouse_stock(
        origin_date,
        dataset.inventory_batches,
        dataset.lanes,
        dataset.skus,
    )
    warehouse_inventory = (
        pd.to_numeric(warehouse_stock["quantity"], errors="coerce")
        .fillna(0)
        .groupby(warehouse_stock["location_id"].astype(str))
        .sum()
        .to_dict()
        if not warehouse_stock.empty
        else {}
    )

    destination_lots = get_destination_lots(
        origin_date,
        horizon_days,
        dataset.inventory_batches,
        dataset.inbound_shipments,
    )
    destination_inventory = (
        destination_lots.groupby("dest_id")["quantity"].sum().to_dict()
        if not destination_lots.empty
        else {}
    )

    risk_by_destination = _risk_by_destination(run.get("risk_alerts"), run_id)

    locations: list[NetworkLocation] = []
    for _, row in dataset.warehouses.iterrows():
        latitude, longitude, coordinate_status = _coordinate(row)
        location_id = str(row["warehouse_id"])
        locations.append(NetworkLocation(
            id=location_id,
            type="warehouse",
            name=str(row["name"]),
            region=str(row["region"]),
            latitude=latitude,
            longitude=longitude,
            coordinate_status=coordinate_status,
            usable_inventory=round(float(warehouse_inventory.get(location_id, 0)), 1),
        ))

    for _, row in dataset.destinations.iterrows():
        latitude, longitude, coordinate_status = _coordinate(row)
        location_id = str(row["dest_id"])
        destination_type = str(row.get("type", "")).strip().lower()
        if destination_type not in {"store", "distributor"}:
            raise DataError(
                message=f"Destination '{location_id}' has an unsupported location type."
            )
        locations.append(NetworkLocation(
            id=location_id,
            type=destination_type,
            name=str(row["name"]),
            region=str(row["region"]),
            latitude=latitude,
            longitude=longitude,
            coordinate_status=coordinate_status,
            usable_inventory=round(float(destination_inventory.get(location_id, 0)), 1),
            risk=risk_by_destination.get(location_id),
        ))

    location_by_id = {location.id: location for location in locations}
    sku_ids = set(dataset.skus["sku_id"].astype(str))
    verification_status = (
        "verified" if (run.get("checker_verdict") or {}).get("passed") is True
        else "unverified"
    )
    flows: list[ShipmentFlow] = []
    seen_line_ids: set[str] = set()
    for line in run.get("plan_lines") or []:
        if not isinstance(line, dict):
            raise DataError(
                message=f"Run '{run_id}' contains a malformed shipment line."
            )
        source_id = str(line.get("warehouse_id", ""))
        destination_id = str(line.get("dest_id", ""))
        sku_id = str(line.get("sku_id", ""))
        line_id = str(line.get("line_id", ""))
        source = location_by_id.get(source_id)
        destination = location_by_id.get(destination_id)
        quantity = line.get("quantity")
        if (
            source is None
            or source.type != "warehouse"
            or destination is None
            or destination.type == "warehouse"
            or sku_id not in sku_ids
            or not line_id
            or line_id in seen_line_ids
        ):
            raise DataError(
                message=f"Run '{run_id}' contains a shipment with an unknown location or SKU reference."
            )
        seen_line_ids.add(line_id)
        try:
            quantity = float(quantity)
            freight_cost_value = line.get("freight_cost")
            freight_cost = (
                None if freight_cost_value is None else float(freight_cost_value)
            )
        except (TypeError, ValueError) as exc:
            raise DataError(
                message=f"Run '{run_id}' contains a shipment with invalid quantity or freight cost."
            ) from exc
        if (
            not math.isfinite(quantity)
            or quantity <= 0
            or (freight_cost is not None and (
                not math.isfinite(freight_cost) or freight_cost < 0
            ))
        ):
            raise DataError(
                message=f"Run '{run_id}' contains a shipment with invalid quantity or freight cost."
            )
        flows.append(ShipmentFlow(
            line_id=line_id,
            source_id=source_id,
            destination_id=destination_id,
            sku_id=sku_id,
            quantity=quantity,
            freight_cost=freight_cost,
            verification_status=verification_status,
        ))

    if dataset_dir.parent == settings.demo_data_dir.resolve():
        dataset_id = f"demo_{dataset_dir.name}"
    else:
        dataset_id = f"dataset_{dataset_hash}"

    return NetworkMapResponse(
        dataset_id=dataset_id,
        dataset_hash=dataset_hash,
        run_id=run_id,
        origin_date=origin_date.isoformat(),
        locations=locations,
        flows=flows,
    )
