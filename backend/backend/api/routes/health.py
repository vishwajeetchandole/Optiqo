"""
Optiqo — GET /api/health
Returns service health and per-component availability.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.schemas.common import AppStatus
from backend.schemas.health import HealthResponse

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns the service status, version, and availability of each component.",
    tags=["Health"],
)
def health_check() -> HealthResponse:
    components: dict[str, str] = {}

    # FastAPI / Uvicorn — always OK if we're responding
    components["fastapi"] = "OK"

    # PuLP / CBC solver availability
    try:
        import pulp  # noqa: F401
        components["pulp_cbc"] = "AVAILABLE"
    except ImportError:
        components["pulp_cbc"] = "UNAVAILABLE"

    # LightGBM availability
    try:
        import lightgbm  # noqa: F401
        components["lightgbm"] = "AVAILABLE"
    except ImportError:
        components["lightgbm"] = "UNAVAILABLE"

    # Dataset readiness — check for the canonical seed=42 demo cache
    demo_dir = settings.demo_data_dir / f"seed_{settings.DEFAULT_SEED}"
    csv_files = list(demo_dir.glob("*.csv")) if demo_dir.exists() else []
    components["dataset"] = "LOADED" if len(csv_files) >= 10 else "NOT_LOADED"

    # Overall health is DEGRADED if any critical component is UNAVAILABLE
    critical_unavailable = any(
        v == "UNAVAILABLE" for k, v in components.items()
        if k in ("fastapi", "pulp_cbc")
    )
    overall = AppStatus.DEGRADED if critical_unavailable else AppStatus.HEALTHY

    logger.debug("Health check: %s | components=%s", overall, components)

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        components=components,
        timestamp=datetime.now(tz=timezone.utc),
    )
