"""
Optiqo — API Tests: All Three Task 2 Endpoints

Tests:
  - GET /api/health → 200, correct structure
  - GET /api/demo-data → 200, 10 tables, correct metadata
  - GET /api/demo-data different seed → different hash, correct metadata
  - GET /api/demo-data force_regenerate only affects requested seed
  - GET /api/demo-data cached on second call
  - POST /api/data/validate (clean) → VALID, planning_blocked=False
  - POST /api/data/validate (missing dataset) → 404
  - POST /api/data/validate (invalid planning_date) → 422
  - POST /api/data/validate with explicit dataset_path
  - Invalid request bodies return appropriate error responses
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── GET /api/health ───────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_response_schema(self, client: TestClient):
        r = client.get("/api/health")
        d = r.json()
        assert "status" in d
        assert d["status"] in ("HEALTHY", "DEGRADED")
        assert "version" in d
        assert "components" in d
        assert "timestamp" in d

    def test_health_components_present(self, client: TestClient):
        r = client.get("/api/health")
        components = r.json().get("components", {})
        assert "fastapi" in components
        assert "pulp_cbc" in components
        assert "lightgbm" in components
        assert "dataset" in components

    def test_health_fastapi_always_ok(self, client: TestClient):
        r = client.get("/api/health")
        assert r.json()["components"]["fastapi"] == "OK"

    def test_health_method_not_allowed(self, client: TestClient):
        r = client.post("/api/health")
        assert r.status_code == 405


# ── GET /api/demo-data ────────────────────────────────────────────────────────

class TestDemoData:
    def test_demo_data_returns_200(self, client: TestClient):
        r = client.get("/api/demo-data")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"

    def test_demo_data_response_schema(self, client: TestClient):
        r = client.get("/api/demo-data")
        d = r.json()
        assert "status" in d
        assert "dataset_id" in d
        assert "dataset_hash" in d
        assert "parameters" in d
        assert "tables" in d
        assert d["status"] == "READY"

    def test_demo_data_10_tables(self, client: TestClient):
        r = client.get("/api/demo-data")
        tables = r.json().get("tables", {})
        assert len(tables) == 10, f"Expected 10 tables, got {len(tables)}: {list(tables)}"

    def test_demo_data_seed_42_defaults(self, client: TestClient):
        r = client.get("/api/demo-data")
        d = r.json()
        assert d["parameters"]["seed"] == 42
        assert d["dataset_id"] == "demo_seed_42"
        assert d["parameters"]["destinations_count"] == 40
        assert d["parameters"]["warehouses_count"] == 4
        assert d["parameters"]["skus_count"] == 30

    def test_demo_data_row_counts(self, client: TestClient):
        r = client.get("/api/demo-data")
        tables = r.json().get("tables", {})
        assert tables.get("skus", {}).get("row_count") == 30
        assert tables.get("warehouses", {}).get("row_count") == 4
        assert tables.get("destinations", {}).get("row_count") == 40
        assert tables.get("lanes", {}).get("row_count") == 160
        assert tables.get("calendar_events", {}).get("row_count") == 420
        assert tables.get("config", {}).get("row_count") == 1

    def test_demo_data_hash_not_empty(self, client: TestClient):
        r = client.get("/api/demo-data")
        h = r.json().get("dataset_hash", "")
        assert len(h) == 64, f"Expected 64-char SHA-256 hex, got: {h!r}"

    def test_demo_data_same_seed_same_hash(self, client: TestClient):
        """Calling with same seed twice must return identical hash."""
        h1 = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        h2 = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        assert h1 == h2, "Same seed must return same hash on repeated calls"

    def test_demo_data_different_seed_different_hash(self, client: TestClient):
        """Seed=42 and seed=7 must produce different hashes."""
        h42 = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        h7 = client.get("/api/demo-data?seed=7").json()["dataset_hash"]
        assert h42 != h7, "Different seeds must produce different hashes"

    def test_demo_data_different_seed_correct_metadata(self, client: TestClient):
        """When seed=7 is requested, returned metadata must reflect seed=7."""
        r = client.get("/api/demo-data?seed=7")
        d = r.json()
        assert d["parameters"]["seed"] == 7
        assert d["dataset_id"] == "demo_seed_7"

    def test_demo_data_force_regenerate_does_not_change_seed_42_hash(self, client: TestClient):
        """force_regenerate for seed=7 must not affect seed=42 data."""
        h42_before = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        # Force regenerate seed=7 (different seed)
        client.get("/api/demo-data?seed=7&force_regenerate=true")
        h42_after = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        assert h42_before == h42_after, \
            "force_regenerate for seed=7 must NOT change seed=42 data"

    def test_demo_data_force_regenerate_same_seed_same_hash(self, client: TestClient):
        """force_regenerate with same seed must produce the same hash (deterministic)."""
        h_before = client.get("/api/demo-data?seed=42").json()["dataset_hash"]
        h_after = client.get("/api/demo-data?seed=42&force_regenerate=true").json()["dataset_hash"]
        assert h_before == h_after, \
            "force_regenerate with the same seed must produce an identical hash"

    def test_demo_data_invalid_seed_rejected(self, client: TestClient):
        """Negative seed must be rejected with 422."""
        r = client.get("/api/demo-data?seed=-1")
        assert r.status_code == 422


# ── POST /api/data/validate ───────────────────────────────────────────────────

class TestValidate:
    def test_validate_clean_dataset_is_valid(self, client: TestClient):
        # Ensure seed=42 demo is available
        client.get("/api/demo-data?seed=42")
        # Use 2024-01-15 as the planning date: early enough in the dataset that
        # all generated batches have valid (future) expiry dates, so the clean
        # dataset produces zero blocking errors regardless of today's date.
        r = client.post("/api/data/validate", json={"planning_date": "2024-01-15"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] in ("VALID", "WARNINGS_ONLY"), \
            f"Clean dataset should be VALID or WARNINGS_ONLY, got {d['status']}. Errors: {d.get('errors')}"
        assert not d["planning_blocked"], \
            f"Clean dataset must not block planning. Errors: {d.get('errors')}"
        assert d["error_count"] == 0

    def test_validate_response_schema(self, client: TestClient):
        r = client.post("/api/data/validate", json={"planning_date": "2024-01-15"})
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert "planning_blocked" in d
        assert "error_count" in d
        assert "warning_count" in d
        assert "errors" in d
        assert "warnings" in d
        assert "summary" in d

    def test_validate_summary_has_10_tables(self, client: TestClient):
        r = client.post("/api/data/validate", json={"planning_date": "2024-01-15"})
        d = r.json()
        assert d["summary"]["total_tables_checked"] == 10

    def test_validate_missing_dataset_returns_404(self, client: TestClient):
        r = client.post("/api/data/validate", json={
            "dataset_path": "r:/Optiqo/nonexistent_dir_xyz"
        })
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        d = r.json()
        assert "code" in d
        assert d["code"] == "DATASET_NOT_FOUND"

    def test_validate_invalid_planning_date_returns_422(self, client: TestClient):
        r = client.post("/api/data/validate", json={
            "planning_date": "not-a-date"
        })
        assert r.status_code == 422

    def test_validate_returns_errors_for_injected_fault(
        self, client: TestClient, corrupted_dataset_dir: Path
    ):
        """Validate a dataset with an injected fault returns planning_blocked=True."""
        import pandas as pd
        skus_path = corrupted_dataset_dir / "skus.csv"
        df = pd.read_csv(skus_path)
        df.loc[0, "unit_volume"] = 0.0  # inject fault 12
        df.to_csv(skus_path, index=False)

        r = client.post("/api/data/validate", json={
            "dataset_path": str(corrupted_dataset_dir),
            "planning_date": "2024-01-15",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["planning_blocked"] is True
        assert d["error_count"] > 0
        fault_rules = [e["rule"] for e in d["errors"]]
        assert "NON_POSITIVE_UNIT_VOLUME" in fault_rules

    def test_validate_errors_have_required_fields(self, client: TestClient, corrupted_dataset_dir: Path):
        """Each error finding must have table, rule, and message."""
        import pandas as pd
        lanes_path = corrupted_dataset_dir / "lanes.csv"
        df = pd.read_csv(lanes_path)
        df.loc[0, "transit_days"] = 0
        df.to_csv(lanes_path, index=False)

        r = client.post("/api/data/validate", json={
            "dataset_path": str(corrupted_dataset_dir),
            "planning_date": "2024-01-15",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["error_count"] > 0, "Expected at least one error (transit_days=0 → fault 13)"
        for error in d.get("errors", []):
            assert "table" in error, f"Missing 'table' field in error: {error}"
            assert "rule" in error, f"Missing 'rule' field in error: {error}"
            assert "message" in error, f"Missing 'message' field in error: {error}"

    def test_validate_planning_blocked_false_for_warnings_only(
        self, client: TestClient, clean_dataset_dir: Path
    ):
        """A dataset with only warnings (no blocking errors) must set planning_blocked=False."""
        r = client.post("/api/data/validate", json={
            "dataset_path": str(clean_dataset_dir),
            # Use an early planning date so all generated batches are still fresh
            "planning_date": "2024-01-15",
        })
        assert r.status_code == 200
        d = r.json()
        # Could be VALID or WARNINGS_ONLY, but never planning_blocked=True
        assert not d["planning_blocked"], \
            f"Warnings-only dataset must not block planning. Errors: {d.get('errors')}"
        assert d["error_count"] == 0, \
            f"Expected 0 errors with early planning_date, got: {d.get('errors')}"

    def test_validate_method_get_not_allowed(self, client: TestClient):
        r = client.get("/api/data/validate")
        assert r.status_code == 405
