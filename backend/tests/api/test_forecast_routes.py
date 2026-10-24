"""
Optiqo — API Tests: POST /api/forecast Endpoint (Phase 4, Plan §4.2 item 4)

Tests:
  - POST /api/forecast with valid origin_date returns 200 and documented schema.
  - POST /api/forecast without origin_date returns 422.
  - POST /api/forecast with invalid origin_date format returns 422.
  - POST /api/forecast with nonexistent dataset_path returns 404.
  - POST /api/forecast caching behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestForecastEndpoint:
    def test_forecast_missing_origin_date_returns_422(self, client: TestClient):
        r = client.post("/api/forecast", json={})
        assert r.status_code == 422

    def test_forecast_invalid_origin_date_returns_422(self, client: TestClient):
        r = client.post("/api/forecast", json={"origin_date": "not-a-valid-date"})
        assert r.status_code == 422
        d = r.json()
        assert "code" in d or "detail" in d

    def test_forecast_nonexistent_dataset_returns_404(self, client: TestClient):
        r = client.post("/api/forecast", json={
            "origin_date": "2024-01-15",
            "dataset_path": "r:/Optiqo/nonexistent_dir_999",
        })
        assert r.status_code == 404
        d = r.json()
        assert d.get("code") == "DATASET_NOT_FOUND"

    def test_forecast_clean_dataset_returns_200(self, client: TestClient, clean_dataset_dir: Path):
        r = client.post("/api/forecast", json={
            "origin_date": "2024-01-15",
            "horizon_days": 7,
            "dataset_path": str(clean_dataset_dir),
            "use_cache": False,
        })
        assert r.status_code == 200
        d = r.json()

        # Check top-level contract fields
        assert "status" in d
        assert d["status"] in ("OK", "FALLBACK_FORECAST")
        assert d["origin_date"] == "2024-01-15"
        assert d["horizon_days"] == 7
        assert "forecast_summary" in d
        assert "forecasts" in d

        summary = d["forecast_summary"]
        assert "total_series" in summary
        assert "methods_used" in summary
        assert "fallbacks_applied" in summary
        assert summary["total_series"] == len(d["forecasts"])

        # Check item fields
        for fc in d["forecasts"]:
            assert "sku_id" in fc
            assert "dest_id" in fc
            assert "method" in fc
            assert "is_fallback" in fc
            assert "daily_forecast" in fc
            assert len(fc["daily_forecast"]) == 7
            assert "horizon_mean" in fc
            assert "scenario_multipliers" in fc
            assert "scenarios" in fc
            assert "low" in fc["scenarios"]
            assert "mid" in fc["scenarios"]
            assert "high" in fc["scenarios"]

    def test_forecast_use_cache(self, client: TestClient, clean_dataset_dir: Path):
        """Second call with use_cache=True should return immediately from in-memory cache."""
        r1 = client.post("/api/forecast", json={
            "origin_date": "2024-01-15",
            "horizon_days": 7,
            "dataset_path": str(clean_dataset_dir),
            "use_cache": True,
        })
        assert r1.status_code == 200

        r2 = client.post("/api/forecast", json={
            "origin_date": "2024-01-15",
            "horizon_days": 7,
            "dataset_path": str(clean_dataset_dir),
            "use_cache": True,
        })
        assert r2.status_code == 200
        assert r1.json()["forecast_summary"] == r2.json()["forecast_summary"]
