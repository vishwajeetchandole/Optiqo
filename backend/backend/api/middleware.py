"""
Optiqo — FastAPI Exception Handler Middleware
Maps OptiqoError subclasses to RFC 7807 Problem Detail JSON responses.
Also adds request-timing to every response header.
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.core.exceptions import OptiqoError
from backend.core.logging import get_logger
from backend.schemas.common import ProblemDetail

logger = get_logger(__name__)

BASE_TYPE_URL = "https://optiqo.vyrox.ai/errors"


async def optiqo_exception_handler(request: Request, exc: OptiqoError) -> JSONResponse:
    """Translate any OptiqoError into an RFC 7807 Problem Details response."""
    problem = ProblemDetail(
        type=f"{BASE_TYPE_URL}/{exc.error_code}",
        title=exc.error_code.replace("_", " ").title(),
        status=exc.http_status,
        detail=exc.message,
        instance=str(request.url.path),
        code=exc.error_code,
        errors=exc.details if exc.details else None,
    )
    logger.warning(
        "OptiqoError [%s] on %s %s: %s",
        exc.error_code, request.method, request.url.path, exc.message,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=problem.model_dump(exclude_none=True),
        headers={"Content-Type": "application/problem+json"},
    )


async def timing_middleware(request: Request, call_next) -> Response:
    """Add X-Process-Time-Ms header to every response."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    return response
