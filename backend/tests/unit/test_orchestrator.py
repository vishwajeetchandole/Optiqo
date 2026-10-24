"""
Optiqo — Single-Cycle Planning Orchestrator Unit Tests (PRD §5.1, Plan §6)

Verifies:
1. Strict stage ordering and clean execution flow.
2. Failure propagation on blocking validation faults.
3. Missing dataset and invalid date error handling.
4. Engine error handling (forecaster error, optimizer infeasibility, solver timeout).
5. Independent constraint violation handling (marking plan UNVERIFIED).
6. End-to-end successful plan execution.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import pandas as pd

from backend.core.exceptions import (
    DataError,
    ForecastError,
    InfeasibleError,
    MissingDatasetError,
    SolverTimeoutError,
    ValidationError,
)
from backend.engines.protocols import (
    ForecastEngineOutput,
    ForecastRequestPayload,
    ForecasterProtocol,
    OptimizerEngineOutput,
    OptimizerProtocol,
    PlannedShipmentLine,
    VerificationResult,
    ConstraintViolation,
)
from backend.schemas.plan import PlanRequest, PlanResponse
from backend.services.orchestrator import run_planning_cycle


class MockFailingForecaster(ForecasterProtocol):
    def generate_forecast(self, payload: ForecastRequestPayload) -> ForecastEngineOutput:
        return ForecastEngineOutput(
            status="ERROR",
            forecast_table=pd.DataFrame(),
            validation_wape_by_method={},
            coverage_rate=0.0,
            diagnostics={"error": "Simulated forecast engine failure"},
        )


class MockInfeasibleOptimizer(OptimizerProtocol):
    def optimize_allocation(
        self, usable_inventory, forecast_table, destinations, skus, lanes, config, origin_date=None
    ) -> OptimizerEngineOutput:
        return OptimizerEngineOutput(
            status="INFEASIBLE",
            objective_value=0.0,
            solver_runtime_seconds=0.1,
            lines=[],
            rounding_loss_units=0,
            unmet_demand_by_dest_sku=pd.DataFrame(),
            expected_expiry_by_dest_sku=pd.DataFrame(),
            slack_data={},
        )


class MockTimeoutOptimizer(OptimizerProtocol):
    def optimize_allocation(
        self, usable_inventory, forecast_table, destinations, skus, lanes, config, origin_date=None
    ) -> OptimizerEngineOutput:
        return OptimizerEngineOutput(
            status="SOLVER_TIMEOUT",
            objective_value=0.0,
            solver_runtime_seconds=60.0,
            lines=[],
            rounding_loss_units=0,
            unmet_demand_by_dest_sku=pd.DataFrame(),
            expected_expiry_by_dest_sku=pd.DataFrame(),
            slack_data={},
        )


class MockFailingVerifier:
    def verify_plan(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=False,
            total_violations=2,
            violations=[
                ConstraintViolation(
                    constraint_id="C1_BATCH_STOCK",
                    entity_id="B_01",
                    violation_message="Allocated units exceed available stock",
                    observed_value=120.0,
                    limit_value=100.0,
                ),
                ConstraintViolation(
                    constraint_id="C4_NON_NEGATIVE_INT",
                    entity_id="L1",
                    violation_message="Fractional allocation",
                    observed_value=12.5,
                    limit_value=1.0,
                ),
            ],
            checked_rules_summary={"C1_BATCH_STOCK": 1, "C4_NON_NEGATIVE_INT": 1},
        )


class TestPlanningOrchestrator:
    def test_invalid_origin_date_raises_data_error(self):
        request = PlanRequest(origin_date="invalid-date")
        with pytest.raises(DataError) as exc_info:
            run_planning_cycle(request)
        assert "Invalid origin_date format" in exc_info.value.message

    def test_missing_dataset_path_raises_missing_dataset_error(self, tmp_path):
        nonexistent_path = tmp_path / "does_not_exist"
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(nonexistent_path))
        with pytest.raises(MissingDatasetError):
            run_planning_cycle(request)

    def test_blocking_validation_fault_aborts_planning(self, clean_dataset_dir: Path, tmp_path: Path):
        """Create a dataset with transit_days = 0 (Fault 13) and verify planning is aborted before forecasting."""
        corrupt_dir = tmp_path / "corrupt_data"
        corrupt_dir.mkdir()
        for f in clean_dataset_dir.glob("*.csv"):
            corrupt_dir.joinpath(f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        # Corrupt lanes.csv
        lanes_file = corrupt_dir / "lanes.csv"
        lanes_df = pd.read_csv(lanes_file)
        lanes_df.loc[0, "transit_days"] = 0
        lanes_df.to_csv(lanes_file, index=False)

        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(corrupt_dir))
        with pytest.raises(ValidationError) as exc_info:
            run_planning_cycle(request)

        assert "blocking errors" in exc_info.value.message
        assert any("TRANSIT_DAYS_BELOW_ONE" in d for d in exc_info.value.details)

    def test_forecaster_failure_raises_forecast_error(self, clean_dataset_dir: Path):
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(clean_dataset_dir))
        with pytest.raises(ForecastError):
            run_planning_cycle(request, forecaster=MockFailingForecaster())

    def test_infeasible_optimizer_raises_infeasible_error(self, clean_dataset_dir: Path):
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(clean_dataset_dir))
        with pytest.raises(InfeasibleError):
            run_planning_cycle(request, optimizer=MockInfeasibleOptimizer())

    def test_solver_timeout_without_lines_raises_timeout_error(self, clean_dataset_dir: Path):
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(clean_dataset_dir))
        with pytest.raises(SolverTimeoutError):
            run_planning_cycle(request, optimizer=MockTimeoutOptimizer())

    def test_verifier_violations_mark_plan_unverified(self, clean_dataset_dir: Path):
        """When the independent verifier finds violations, plan is marked UNVERIFIED with violations reported."""
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(clean_dataset_dir))
        response = run_planning_cycle(request, verifier=MockFailingVerifier())

        assert response.status == "UNVERIFIED"
        assert response.checker_status.passed is False
        assert response.checker_status.violations_count == 2
        assert len(response.checker_status.violations) == 2
        assert response.checker_status.violations[0].constraint_id == "C1_BATCH_STOCK"
        assert response.checker_status.violations[1].constraint_id == "C4_NON_NEGATIVE_INT"

    def test_successful_end_to_end_planning_cycle(self, clean_dataset_dir: Path):
        """Clean execution: verifies the full 9-step sequence produces a valid, verified plan."""
        request = PlanRequest(origin_date="2024-01-15", dataset_path=str(clean_dataset_dir))
        response = run_planning_cycle(request)

        assert isinstance(response, PlanResponse)
        assert response.status == "OK"
        assert response.origin_date == "2024-01-15"
        assert response.checker_status.passed is True
        assert response.checker_status.violations_count == 0
        assert response.summary.total_shipped_units >= 0
        assert response.summary.total_freight_cost >= 0.0
        assert response.summary.expected_unmet_demand_before >= 0.0
        assert response.summary.expected_unmet_demand_after >= 0.0
        assert response.summary.supply_bound_unavoidable_shortage >= 0.0
        assert len(response.plan_lines) > 0
        for line in response.plan_lines:
            assert line.explanation is not None
            assert line.explanation.evidence is not None
            assert len(line.explanation.sentence) > 0
