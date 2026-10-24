# Optiqo AI/ML engine

This directory is the `aiml` Python package. It provides demand forecasting,
inventory allocation, independent verification, explanations, and offline
evaluation. The FastAPI application lives in `backend/`.

## Implemented

- Strict validation for demand, inventory, lanes, costs, capacities, and
  forecast frames.
- Chronological train/validation/test partitions and leakage-safe features.
- Seasonal-naive and moving-average baselines, with optional LightGBM training
  when its native runtime is available.
- Batch/route/shelf-life eligibility and joint allocation across destinations
  sharing inventory.
- Independent plan verification, evidence-grounded explanations, allocation
  metrics, and deterministic policy benchmarks.

Forecast model selection uses validation MAE; validation also reports WAPE and
signed bias. The held-out test partition is reserved for uncertainty residual
calibration. The engine makes no production accuracy or cost-saving claims.

## Run tests

From this directory, with the package's parent on `PYTHONPATH` (the test
`conftest.py` sets this up):

```powershell
python -m pytest tests -q
```

The end-to-end test exercises forecasting, eligibility, allocation,
verification, explanation, and benchmarking using deterministic synthetic
data.

## Run the engine demo

From the repository root:

```powershell
.\aiml\.venv\Scripts\python.exe -m aiml --demo
```

The demo prints JSON containing the selected model, validation metrics,
forecast horizon, solver outcome, independent-check result, and benchmark
metrics. Data are synthetic and are not production results.

To launch the optional desktop UI, use `.\aiml\.venv\Scripts\python.exe -m
aiml --ui` from the repository root. The UI requires a graphical desktop
session.

## Environment notes

- Runtime and test dependencies are pinned in `requirements.txt`.
- PuLP 2.x and 4.x variable-registration APIs are supported.
- LightGBM may fall back to an identified baseline when its native runtime
  cannot load; this is reported by the engine.

## Public entry points

- `aiml.forecasting.select_and_train` and
  `aiml.forecasting.forecast_seven_day`
- `aiml.optimization.eligible_shipments` and
  `aiml.optimization.optimize_allocation`
- `aiml.optimization.verify_allocation` and
  `aiml.optimization.explain_allocation`
- `aiml.evaluation.allocation_metrics` and
  `aiml.evaluation.run_benchmark`

Column names and the default horizon are configurable through `EngineConfig`.
See [AUDIT_REPORT.md](./AUDIT_REPORT.md) for implementation evidence and
remaining limitations.
