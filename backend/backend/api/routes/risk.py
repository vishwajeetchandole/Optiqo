"""
Optiqo — Risk Routes
  GET /api/risk → Retrieve ranked inventory & supply risk alerts (PRD §5.1 P0-07, §10.6)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from backend.core.config import settings
from backend.core.exceptions import DataError, MissingDatasetError
from backend.core.logging import get_logger
from backend.schemas.risk import RiskOverviewResponse
from backend.services.risk import compute_risk_overview

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/risk",
    response_model=RiskOverviewResponse,
    summary="Retrieve ranked inventory and supply risk alerts",
    description=(
        "Evaluates destination-SKU inventory risks using PRD §10.6 formulations: "
        "days of cover, unmet demand share, expected expiry loss, and financial exposure. "
        "Alerts are ranked by financial exposure with unmet share as tie-breaker. "
        "Identifies network-wide supply shortage SKUs."
    ),
    tags=["Risk"],
)
def get_risk_overview(
    origin_date: str = Query(
        ...,
        description="ISO-8601 planning origin date (YYYY-MM-DD).",
        examples=["2024-01-15"],
    ),
    run_id: Optional[str] = Query(
        default=None,
        description="Optional run ID to inspect post-plan risk state (reserved for Phase 5/7).",
    ),
    dataset_path: Optional[str] = Query(
        default=None,
        description="Optional path to dataset folder. Defaults to cached demo_data (seed_42).",
    ),
) -> RiskOverviewResponse:
    # 1. Validate date format
    try:
        parsed_date = date.fromisoformat(origin_date)
    except ValueError:
        raise DataError(
            message=f"Invalid origin_date format: '{origin_date}'. Expected ISO-8601 YYYY-MM-DD."
        )

    # 2. Resolve dataset directory
    if dataset_path:
        data_dir = Path(dataset_path)
        if not data_dir.is_absolute():
            data_dir = settings.BASE_DIR / dataset_path
    else:
        data_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"

    if not data_dir.exists():
        raise MissingDatasetError(
            message=f"Dataset directory not found: {data_dir}. "
                    "Call GET /api/demo-data first to generate the demo dataset."
        )

    logger.info("Computing risk overview for origin_date=%s from %s", origin_date, data_dir)

    response = compute_risk_overview(
        origin_date=parsed_date,
        dataset_dir=data_dir,
    )
    return response
