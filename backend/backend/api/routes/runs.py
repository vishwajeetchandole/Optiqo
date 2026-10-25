"""
Optiqo — Run Storage & Export API Routes (PRD §5.1 P0-11, §6.7, Plan §4.8, §4.9)
  GET /api/runs/{run_id}         → Retrieve run manifest and audit metadata
  GET /api/runs/{run_id}/export  → Export sanitized plan, risk alerts, or KPIs (CSV/JSON)
"""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Query, Response

from backend.core.exceptions import DataError
from backend.core.logging import get_logger
from backend.schemas.runs import RunManifest
from backend.schemas.network_map import NetworkMapResponse
from backend.services.network_map import get_network_map
from backend.storage.exporter import export_run_artifact
from backend.storage.repository import get_run, list_runs

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/runs",
    summary="List stored planning and backtesting runs",
    description="Returns metadata summaries of all persisted execution runs.",
    tags=["Runs & Exports"],
)
def get_all_runs() -> list[dict]:
    """Retrieve metadata list of all stored runs."""
    return list_runs()


@router.get(
    "/runs/{run_id}",
    response_model=RunManifest,
    summary="Retrieve full run manifest and audit record",
    description=(
        "Retrieves the immutable execution manifest for a given run_id, including "
        "dataset SHA-256 fingerprint, software dependencies, parameter snapshot, "
        "solver status, checker verdict, summary metrics, and plan lines."
    ),
    tags=["Runs & Exports"],
)
def get_run_by_id(run_id: str) -> RunManifest:
    """Retrieve complete run manifest by run_id."""
    logger.info("Fetching run manifest: %s", run_id)
    run_dict = get_run(run_id)
    return RunManifest.model_validate(run_dict)


@router.get(
    "/runs/{run_id}/network",
    response_model=NetworkMapResponse,
    summary="Retrieve the dataset network and shipment flows for a plan run",
    description=(
        "Returns dataset locations, available inventory, persisted pre-plan destination risk summaries, "
        "and shipment allocations from the specified plan run. Coordinates are null "
        "when the dataset does not contain valid latitude and longitude values."
    ),
    tags=["Runs & Exports"],
)
def get_run_network(run_id: str) -> NetworkMapResponse:
    return get_network_map(run_id)


@router.get(
    "/runs/{run_id}/export",
    summary="Export run artifacts in sanitized CSV or JSON format",
    description=(
        "Exports plan lines, risk alerts, or comparative KPIs. CSV outputs feature "
        "formula injection neutralization (PRD §14 N8), automatically quoting cells "
        "beginning with '=', '+', '-', '@', '\\t', or '\\r'."
    ),
    tags=["Runs & Exports"],
)
def export_run_artifact_endpoint(
    run_id: str,
    format: str = Query(
        default="csv",
        description="Export format: 'csv' (streamed CSV) or 'json' (structured JSON).",
        examples=["csv", "json"],
    ),
    artifact: str = Query(
        default="plan",
        description="Target artifact: 'plan' (shipment lines), 'risks' (risk evaluation), or 'kpis' (KPI tables).",
        examples=["plan", "risks", "kpis"],
    ),
) -> Response:
    """Export sanitized run artifact."""
    logger.info("Exporting run artifact: run_id=%s, artifact=%s, format=%s", run_id, artifact, format)

    # 1. Fetch run data
    run_data = get_run(run_id)

    # 2. Generate artifact content
    content_str, media_type = export_run_artifact(
        run_data=run_data,
        artifact=artifact,
        export_format=format,
    )

    # 3. Build filename and headers
    ext = "csv" if format.lower() == "csv" else "json"
    filename = f"{run_id}_{artifact}.{ext}"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Artifact-Type": artifact,
        "X-Export-Format": format,
    }

    return Response(content=content_str, media_type=media_type, headers=headers)
