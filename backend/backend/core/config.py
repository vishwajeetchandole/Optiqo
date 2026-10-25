"""
Optiqo — Application Configuration
Reads from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "Optiqo"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"  # development | staging | production

    # ── API ──────────────────────────────────────────────────────────────────
    API_PREFIX: str = "/api"

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g. "http://localhost:5173"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Paths ─────────────────────────────────────────────────────────────────
    # The config lives at backend/backend/core/config.py; the repository root is four parents up.
    BASE_DIR: Path = Path(__file__).resolve().parents[3]

    @property
    def backend_dir(self) -> Path:
        return self.BASE_DIR / "backend"

    @property
    def demo_data_dir(self) -> Path:
        """Directory that holds the 10 generated CSV tables for the demo dataset."""
        return self.backend_dir / "data" / "demo_data"

    @property
    def runs_dir(self) -> Path:
        """Root directory for persisted run manifests and plan artefacts."""
        return self.backend_dir / "runs"

    @property
    def uploads_dir(self) -> Path:
        """Root directory for uploaded user datasets."""
        return self.backend_dir / "data" / "uploads"

    # ── Dataset generation ───────────────────────────────────────────────────
    DEFAULT_SEED: int = 42
    N_WAREHOUSES: int = 4
    N_DESTINATIONS: int = 40
    N_SKUS: int = 30
    N_DAYS: int = 420          # History length (PRD §11.3)
    N_CATEGORIES: int = 5

    # ── Planning defaults ────────────────────────────────────────────────────
    DEFAULT_HORIZON_DAYS: int = 7
    DEFAULT_BASELINE_SAFETY_DAYS: int = 2
    DEFAULT_SHORTAGE_PENALTY_FACTOR: float = 1.5
    DEFAULT_HOLDING_COST_RATE: float = 0.02
    DEFAULT_LANE_PRUNING_K: int = 3
    DEFAULT_SOLVER_TIMEOUT_SECONDS: int = 60
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 25 * 1024 * 1024

    # ── Simulation ───────────────────────────────────────────────────────────
    EVAL_WINDOW_DAYS: int = 56  # 8 weekly dispatch cycles (PRD §7.1)

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


# Singleton instance consumed across the application
settings = Settings()
