"""
Optiqo — Structured Logging Setup
Configures a consistent log format used across all backend modules.
"""

import logging
import sys

from backend.core.config import settings


def configure_logging() -> None:
    """Configure root logger and suppress noisy third-party loggers."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress overly verbose third-party loggers
    for noisy in ("uvicorn.access", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call configure_logging() once on startup."""
    return logging.getLogger(name)
