"""
Optiqo — API Tests: GET /api/risk Endpoint (Phase 3)

Tests:
  - GET /api/risk with valid origin_date returns 200 and documented schema.
  - GET /api/risk without origin_date returns 422.
  - GET /api/risk with invalid origin_date returns 422.
  - GET /api/risk with nonexistent dataset_path returns 404.
  - Alerts are properly ranked by financial_exposure descending.
  - Response fields conform to RiskOverviewResponse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRiskEndpoint:
    def test_risk_missing_origin_date_returns_422(self, client: TestClient):
        r = client.get("/api/risk")
        assert r.status_code == 422

    def test_risk_invalid_date_format_returns_422(self, client: TestClient):
        r = client.get("/api/risk?origin_date=invalid-date-format")
        assert r.status_code == 422
        d = r.json()
        assert "code" in d or "detail" in d

    def test_risk_nonexistent_dataset_returns_404(self, client: TestClient):
        r = client.get("/api/risk?origin_date=2024-01-15&dataset_path=r:/Optiqo/nonexistent_xyz")
        assert r.status_code == 404
        d = r.json()
        assert d.get("code") == "DATASET_NOT_FOUND"

    def test_risk_clean_dataset_returns_200(self, client: TestClient, clean_dataset_dir: Path):
        r = client.get(f"/api/risk?origin_date=2024-01-15&dataset_path={clean_dataset_dir}")
        assert r.status_code == 200
        d = r.json()

        # Check top-level contract fields
        assert "origin_date" in d
        assert d["origin_date"] == "2024-01-15"
        assert "total_alerts" in d
        assert "high_severity_count" in d
        assert "medium_severity_count" in d
        assert "low_severity_count" in d
        assert "supply_shortage_skus" in d
        assert "alerts" in d

        # Check counts consistency
        assert d["total_alerts"] == len(d["alerts"])
        assert d["high_severity_count"] + d["medium_severity_count"] + d["low_severity_count"] == d["total_alerts"]

        # Check alert item fields
        for alert in d["alerts"]:
            assert "dest_id" in alert
            assert "sku_id" in alert
            assert alert["severity"] in ("HIGH", "MEDIUM", "LOW")
            assert "financial_exposure" in alert
            assert "days_of_cover" in alert
            assert "expected_unmet_units" in alert
            assert "unmet_share_pct" in alert
            assert "expected_expiry_units" in alert
            assert "expected_expiry_loss_cost" in alert
            assert "excess_units" in alert
            assert "is_supply_shortage" in alert
            assert "primary_driver" in alert

    def test_risk_alerts_are_ranked_by_financial_exposure_desc(
        self, client: TestClient, clean_dataset_dir: Path
    ):
        r = client.get(f"/api/risk?origin_date=2024-01-15&dataset_path={clean_dataset_dir}")
        assert r.status_code == 200
        alerts = r.json().get("alerts", [])

        exposures = [a["financial_exposure"] for a in alerts]
        assert exposures == sorted(exposures, reverse=True)
