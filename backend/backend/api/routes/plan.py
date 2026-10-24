"""
Optiqo — Plan Route (PRD §5.1 P0-05, §10.5, Plan §4.5)
  POST /api/plan → Execute single-cycle optimization, independent verification & grounded explanations.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.logging import get_logger
from backend.schemas.plan import PlanRequest, PlanResponse
from backend.services.orchestrator import run_planning_cycle

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Execute single-cycle distribution planning",
    description=(
        "Executes end-to-end distribution planning cycle for a given origin date: "
        "validates dataset, prepares inventory, generates demand forecasts and scenarios, "
        "solves lot-by-lot linear program with integer rounding, performs independent "
        "hard-constraint verification (C1–C5), and synthesizes grounded explanations (PRD §10.5)."
    ),
    tags=["Planning"],
)
def create_distribution_plan(body: PlanRequest) -> PlanResponse:
    """Execute single-cycle planning orchestrator and return verified plan response."""
    logger.info("Received POST /api/plan for origin_date=%s", body.origin_date)
    return run_planning_cycle(request=body)
