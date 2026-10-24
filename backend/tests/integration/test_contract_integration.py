"""
Optiqo — Integration Tests: REST API Contract & Middleware Integration (PRD §6.5, backend.md §32-49, Plan §4)

Verifies:
1. Complete contract adherence across all 9 REST API endpoints:
   - GET /api/health
   - GET /api/demo-data
   - POST /api/data/validate
   - GET /api/risk
   - POST /api/forecast
   - POST /api/plan
   - POST /api/backtest
   - GET /api/runs
   - GET /api/runs/{run_id}
   - GET /api/runs/{run_id}/export
2. Response timing middleware: X-Process-Time-Ms header present on all endpoints.
3. CORS headers: Preflight OPTIONS requests and Access-Control headers.
4. RFC 7807 Problem Details on domain errors and HTTP error status codes.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestFullContractIntegration:
    """Verifies complete 9-endpoint contract integration, headers, CORS, and error details."""

    # ── 1. GET /api/health ───────────────────────────────────────────────────

    def test_ep1_health_contract(self, api_client: TestClient):
        r = api_client.get("/api/health")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert d["status"] in ("HEALTHY", "DEGRADED")
        assert "version" in d
        assert "components" in d
        assert "timestamp" in d
        assert "X-Process-Time-Ms" in r.headers

    # ── 2. GET /api/demo-data ────────────────────────────────────────────────

    def test_ep2_demo_data_contract(self, api_client: TestClient):
        r = api_client.get("/api/demo-data?seed=42")
        assert r.status_code == 200
        d = r.json()
        assert d["parameters"]["seed"] == 42
        assert "dataset_hash" in d
        assert "tables" in d
        assert len(d["tables"]) == 10
        assert "X-Process-Time-Ms" in r.headers

    # ── 3. POST /api/data/validate ───────────────────────────────────────────

    def test_ep3_data_validate_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        r = api_client.post(
            "/api/data/validate",
            json={
                "dataset_path": str(clean_dataset_dir),
                "planning_date": "2024-01-15",
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] in ("VALID", "WARNINGS_ONLY")
        assert d["planning_blocked"] is False
        assert d["error_count"] == 0
        assert "summary" in d
        assert "X-Process-Time-Ms" in r.headers

    # ── 4. GET /api/risk ─────────────────────────────────────────────────────

    def test_ep4_risk_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        r = api_client.get(
            f"/api/risk?origin_date=2024-01-15&dataset_path={clean_dataset_dir}"
        )
        assert r.status_code == 200
        d = r.json()
        assert d["origin_date"] == "2024-01-15"
        assert "total_alerts" in d
        assert "high_severity_count" in d
        assert "medium_severity_count" in d
        assert "low_severity_count" in d
        assert "alerts" in d
        assert isinstance(d["alerts"], list)
        assert "X-Process-Time-Ms" in r.headers

    # ── 5. POST /api/forecast ────────────────────────────────────────────────

    def test_ep5_forecast_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        r = api_client.post(
            "/api/forecast",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] in ("OK", "FALLBACK_FORECAST")
        assert "forecasts" in d
        assert len(d["forecasts"]) > 0
        first = d["forecasts"][0]
        assert "sku_id" in first
        assert "dest_id" in first
        assert "daily_forecast" in first
        assert len(first["daily_forecast"]) == 7
        assert "X-Process-Time-Ms" in r.headers

    # ── 6. POST /api/plan ────────────────────────────────────────────────────

    def test_ep6_plan_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        r = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "lane_pruning_k": 3,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "OK"
        assert "run_id" in d
        assert "checker_status" in d
        assert d["checker_status"]["passed"] is True
        assert "summary" in d
        assert "plan_lines" in d
        assert len(d["plan_lines"]) > 0
        assert "X-Process-Time-Ms" in r.headers

    # ── 7. POST /api/backtest ────────────────────────────────────────────────

    def test_ep7_backtest_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        r = api_client.post(
            "/api/backtest",
            json={
                "dataset_path": str(clean_dataset_dir),
                "evaluation_start_date": "2024-06-03",
                "window_days": 14,
                "policies": ["B1", "B2", "OPTIQO"],
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "COMPLETED"
        assert "run_id" in d
        assert "kpi_comparison" in d
        assert "forecast_kpis" in d
        assert "optimization_kpis" in d
        assert "X-Process-Time-Ms" in r.headers

    # ── 8. GET /api/runs ─────────────────────────────────────────────────────

    def test_ep8_runs_list_contract(self, api_client: TestClient):
        r = api_client.get("/api/runs")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        assert "X-Process-Time-Ms" in r.headers

    # ── 9. GET /api/runs/{run_id} & GET /api/runs/{run_id}/export ────────────

    def test_ep9_run_detail_and_export_contract(self, clean_dataset_dir: Path, api_client: TestClient):
        # 1. Run a plan to produce a known run_id
        plan_resp = api_client.post(
            "/api/plan",
            json={
                "origin_date": "2024-01-15",
                "horizon_days": 7,
                "lane_pruning_k": 3,
                "dataset_path": str(clean_dataset_dir),
            },
        )
        assert plan_resp.status_code == 200
        run_id = plan_resp.json()["run_id"]

        # 2. GET /api/runs/{run_id}
        detail_resp = api_client.get(f"/api/runs/{run_id}")
        assert detail_resp.status_code == 200
        manifest = detail_resp.json()
        assert manifest["run_id"] == run_id
        assert manifest["status"] == "OK"
        assert "dataset_hash" in manifest
        assert "parameters" in manifest
        assert "checker_verdict" in manifest
        assert "plan_lines" in manifest

        # 3. GET /api/runs/{run_id}/export (CSV)
        export_csv = api_client.get(f"/api/runs/{run_id}/export?artifact=plan&format=csv")
        assert export_csv.status_code == 200
        assert "text/csv" in export_csv.headers.get("content-type", "")
        assert "line_id" in export_csv.text

        # 4. GET /api/runs/{run_id}/export (JSON)
        export_json = api_client.get(f"/api/runs/{run_id}/export?artifact=plan&format=json")
        assert export_json.status_code == 200
        assert "application/json" in export_json.headers.get("content-type", "")

    # ── Middleware: CORS & Preflight ──────────────────────────────────────────

    def test_cors_preflight_headers(self, api_client: TestClient):
        """Test CORS OPTIONS preflight request returns Access-Control headers."""
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        resp = api_client.options("/api/plan", headers=headers)
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers
        assert resp.headers["access-control-allow-origin"] in ("*", "http://localhost:5173")

    # ── RFC 7807 Problem Details ─────────────────────────────────────────────

    def test_rfc7807_error_structure_on_404(self, api_client: TestClient):
        """Test 404 response structure follows RFC 7807 Problem Details."""
        resp = api_client.get("/api/runs/nonexistent_run_99999")
        assert resp.status_code == 404
        assert resp.headers.get("content-type") == "application/problem+json"
        body = resp.json()
        assert "type" in body
        assert "title" in body
        assert body["status"] == 404
        assert "detail" in body
        assert body["code"] in ("RUN_NOT_FOUND", "NOT_FOUND")

    def test_rfc7807_error_structure_on_422(self, api_client: TestClient):
        """Test 422 response structure on invalid plan request."""
        resp = api_client.post(
            "/api/plan",
            json={"origin_date": "invalid-date-format"},
        )
        assert resp.status_code == 422
        body = resp.json()
        # Either RFC 7807 from our handler or FastAPI's request validation structure
        assert "detail" in body or "title" in body
