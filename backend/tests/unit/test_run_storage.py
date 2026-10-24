"""
Optiqo — Run Storage & Export Unit Tests (PRD §5.1 P0-11, §6.7, §14 N7, N8, Plan §7)

Tests:
1. Atomic save and retrieval of RunManifest in repository.
2. Missing run_id raises RunNotFoundError (HTTP 404).
3. Path safety / directory traversal rejection (e.g. '../../etc/passwd').
4. Dataset SHA-256 fingerprinting deterministic and sensitive to file content.
5. Formula injection neutralization:
   - Prepends single quote to cells beginning with '=', '+', '-', '@', '\\t', '\\r'.
   - Neutralizes malicious strings like '=1+1', '+cmd', '-cmd', '@SUM', etc.
   - Preserves genuine numeric values, including negative floats/ints (-15.2, -5).
6. Artifact exports for 'plan', 'risks', 'kpis' in both 'csv' and 'json'.
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from backend.core.exceptions import DataError, RunNotFoundError
from backend.schemas.runs import RunManifest
from backend.storage.exporter import (
    dataframe_to_sanitized_csv,
    export_run_artifact,
    sanitize_csv_cell,
)
from backend.storage.repository import (
    compute_dataset_hash,
    get_run,
    list_runs,
    save_run,
    validate_safe_run_id,
)


class TestRunStorage:
    def test_save_and_get_run(self, tmp_path: Path):
        """Test atomic save and retrieval of a run manifest."""
        test_dir = tmp_path / "runs"

        manifest = RunManifest(
            run_id="run_20240115_test0001",
            run_type="PLAN",
            origin_date="2024-01-15",
            dataset_hash="abcd1234efgh5678",
            seed=42,
            parameters={"horizon_days": 7, "lane_pruning_k": 3},
            status="OK",
            solver_status="OPTIMAL",
            solver_runtime_seconds=1.25,
            summary={"total_shipped_units": 500, "total_freight_cost": 250.0},
            plan_lines=[
                {
                    "line_id": "line_0001",
                    "warehouse_id": "WH_01",
                    "batch_id": "B_001",
                    "sku_id": "SKU_001",
                    "dest_id": "DEST_001",
                    "quantity": 100,
                    "arrival_date": "2024-01-16",
                    "total_freight_cost": 50.0,
                    "explanation": {"sentence": "Shipped from WH_01 due to proximity."},
                }
            ],
        )

        saved_path = save_run(manifest, runs_dir=test_dir)
        assert saved_path.exists()
        assert saved_path.name == "run_20240115_test0001.json"

        loaded = get_run("run_20240115_test0001", runs_dir=test_dir)
        assert loaded["run_id"] == "run_20240115_test0001"
        assert loaded["run_type"] == "PLAN"
        assert loaded["dataset_hash"] == "abcd1234efgh5678"
        assert loaded["status"] == "OK"
        assert loaded["summary"]["total_shipped_units"] == 500
        assert len(loaded["plan_lines"]) == 1

        # Test list_runs
        summaries = list_runs(runs_dir=test_dir)
        assert len(summaries) >= 1
        assert any(s["run_id"] == "run_20240115_test0001" for s in summaries)

    def test_missing_run_raises_404(self, tmp_path: Path):
        """Test non-existent run_id raises RunNotFoundError."""
        test_dir = tmp_path / "runs"

        with pytest.raises(RunNotFoundError) as exc_info:
            get_run("non_existent_run_99999", runs_dir=test_dir)
        assert exc_info.value.http_status == 404

    def test_path_traversal_prevention(self, tmp_path: Path):
        """Test malicious path traversal run_ids are strictly rejected."""
        test_dir = tmp_path / "runs"

        malicious_ids = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "../secret",
            "run/with/slashes",
            "run\\with\\backslashes",
            "run with spaces",
            "run;drop table",
        ]

        for bad_id in malicious_ids:
            with pytest.raises(RunNotFoundError):
                get_run(bad_id, runs_dir=test_dir)

            with pytest.raises(RunNotFoundError):
                save_run({"run_id": bad_id}, runs_dir=test_dir)

    def test_compute_dataset_hash(self, tmp_path: Path):
        """Test dataset SHA-256 fingerprinting is deterministic and content-sensitive."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        (data_dir / "skus.csv").write_text("sku_id,name\nSKU_001,Juice\n", encoding="utf-8")
        (data_dir / "lanes.csv").write_text("wh,dest\nWH_01,DEST_01\n", encoding="utf-8")

        hash1 = compute_dataset_hash(data_dir)
        hash2 = compute_dataset_hash(data_dir)
        assert hash1 == hash2
        assert len(hash1) == 16

        # Modifying content must change hash
        (data_dir / "skus.csv").write_text("sku_id,name\nSKU_001,Soda\n", encoding="utf-8")
        hash3 = compute_dataset_hash(data_dir)
        assert hash1 != hash3


class TestSanitizedExporter:
    def test_formula_injection_neutralization(self):
        """Test formula triggers =, +, -, @, \\t, \\r are prefixed with single quote."""
        malicious_inputs = [
            ("=SUM(A1:B10)", "'=SUM(A1:B10)"),
            ("=1+1", "'=1+1"),
            ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
            ("-cmd|' /C calc'!A0", "'-cmd|' /C calc'!A0"),
            ("@SUM(A1)", "'@SUM(A1)"),
            ("\tmalicious_tab", "'\tmalicious_tab"),
            ("\rmalicious_cr", "'\rmalicious_cr"),
            ("-2+3+cmd", "'-2+3+cmd"),
        ]

        for raw_val, expected in malicious_inputs:
            sanitized = sanitize_csv_cell(raw_val)
            assert sanitized == expected, f"Failed for {raw_val}: got {sanitized}"

    def test_numeric_preservation(self):
        """Test genuine numeric values (including negative numbers) remain numeric."""
        numerics = [
            (0, 0),
            (100, 100),
            (-5, -5),
            (25.5, 25.5),
            (-15.2, -15.2),
            ("-15.2", "-15.2"),  # pure numeric string preserved
            ("-42", "-42"),
            (True, True),
            (False, False),
            (None, ""),
        ]

        for val, expected in numerics:
            res = sanitize_csv_cell(val)
            assert res == expected, f"Failed for numeric {val}: got {res}"

    def test_export_plan_artifact(self):
        """Test exporting plan artifact in CSV and JSON formats."""
        run_data = {
            "run_id": "run_test_plan",
            "origin_date": "2024-01-15",
            "status": "OK",
            "summary": {"total_shipped_units": 150, "total_freight_cost": 75.0},
            "plan_lines": [
                {
                    "line_id": "L1",
                    "warehouse_id": "WH_01",
                    "batch_id": "B1",
                    "sku_id": "SKU_01",
                    "dest_id": "DEST_01",
                    "quantity": 150,
                    "arrival_date": "2024-01-17",
                    "total_freight_cost": 75.0,
                    "explanation": {
                        "sentence": "=Malicious formula in explanation",
                        "evidence": {"next_best_warehouse": "WH_02"},
                    },
                }
            ],
        }

        # 1. JSON export
        content_json, media_json = export_run_artifact(run_data, artifact="plan", export_format="json")
        assert media_json == "application/json"
        data_json = json.loads(content_json)
        assert data_json["run_id"] == "run_test_plan"
        assert len(data_json["plan_lines"]) == 1

        # 2. CSV export
        content_csv, media_csv = export_run_artifact(run_data, artifact="plan", export_format="csv")
        assert media_csv == "text/csv"
        # Verify formula injection was neutralized in CSV output
        assert "'=Malicious formula in explanation" in content_csv
        assert "WH_01" in content_csv
        assert "150" in content_csv

    def test_export_risks_and_kpis_artifacts(self):
        """Test exporting risks and kpis artifacts."""
        run_data = {
            "run_id": "run_test_metrics",
            "summary": {
                "expected_unmet_demand_before": 100.0,
                "expected_unmet_demand_after": 20.0,
            },
            "kpi_comparison": {
                "unmet_demand_rate_k1": {"b1": 0.068, "optiqo": 0.032},
            },
            "forecast_kpis": {"daily_wape_f1": 0.22},
            "optimization_kpis": {"constraint_violations_o1": 0},
        }

        # Risks CSV & JSON
        risks_csv, media_r_csv = export_run_artifact(run_data, artifact="risks", export_format="csv")
        assert media_r_csv == "text/csv"
        assert "expected_unmet_demand_before" in risks_csv

        risks_json, media_r_json = export_run_artifact(run_data, artifact="risks", export_format="json")
        assert media_r_json == "application/json"

        # KPIs CSV & JSON
        kpis_csv, media_k_csv = export_run_artifact(run_data, artifact="kpis", export_format="csv")
        assert media_k_csv == "text/csv"
        assert "unmet_demand_rate_k1" in kpis_csv

        kpis_json, media_k_json = export_run_artifact(run_data, artifact="kpis", export_format="json")
        assert media_k_json == "application/json"

    def test_invalid_export_parameters_raise_422(self):
        """Test invalid artifact or format raises DataError."""
        run_data = {"run_id": "run_001"}

        with pytest.raises(DataError) as exc_fmt:
            export_run_artifact(run_data, artifact="plan", export_format="xml")
        assert exc_fmt.value.http_status == 422

        with pytest.raises(DataError) as exc_art:
            export_run_artifact(run_data, artifact="invalid_artifact", export_format="csv")
        assert exc_art.value.http_status == 422
