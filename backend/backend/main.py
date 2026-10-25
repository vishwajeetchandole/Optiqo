"""
Optiqo Backend — FastAPI Application Entry Point

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.middleware import optiqo_exception_handler, timing_middleware
from backend.api.routes import backtest as backtest_routes
from backend.api.routes import data as data_routes
from backend.api.routes import forecast as forecast_routes
from backend.api.routes import health as health_routes
from backend.api.routes import plan as plan_routes
from backend.api.routes import risk as risk_routes
from backend.api.routes import runs as runs_routes
from backend.core.config import settings
from backend.core.exceptions import OptiqoError
from backend.core.logging import configure_logging, get_logger

# Configure logging before anything else
configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered FMCG Distribution Intelligence & Inventory Optimization Engine. "
            "Developed by Team VYROX for Triwizathon 2026."
        ),
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Configured origins are allowed everywhere; local Vite ports are dev-only.
    dev_origin_regex = (
        r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?"
        if settings.APP_ENV.lower() == "development"
        else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=dev_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ────────────────────────────────────────────
    app.add_middleware(BaseHTTPMiddleware, dispatch=timing_middleware)

    # ── Domain exception handler ─────────────────────────────────────────────
    app.add_exception_handler(OptiqoError, optiqo_exception_handler)

    # ── Routes ───────────────────────────────────────────────────────────────
    app.include_router(health_routes.router, prefix=settings.API_PREFIX)
    app.include_router(data_routes.router, prefix=settings.API_PREFIX)
    app.include_router(risk_routes.router, prefix=settings.API_PREFIX)
    app.include_router(forecast_routes.router, prefix=settings.API_PREFIX)
    app.include_router(plan_routes.router, prefix=settings.API_PREFIX)
    app.include_router(backtest_routes.router, prefix=settings.API_PREFIX)
    app.include_router(runs_routes.router, prefix=settings.API_PREFIX)

    logger.info(
        "%s v%s starting in %s mode (CORS origins: %s)",
        settings.APP_NAME, settings.APP_VERSION,
        settings.APP_ENV, settings.cors_origins_list,
    )
    return app


app = create_app()
