# Optiqo API contract

## Base URL

`http://localhost:8000/api`

## Health

### `GET /api/health`

Returns service status and component availability.

## Demo data

### `GET /api/demo-data`

Returns generated dataset metadata and table counts for a deterministic seed.

Query parameters:
- `seed` (optional integer, default `42`)
- `force_regenerate` (optional boolean)

## Data validation

### `POST /api/data/validate`

Validates the loaded dataset and returns blocking errors and warnings.

Request body:
- `planning_date` (ISO-8601 date, optional)
- `dataset_path` (string, optional)
- `exclude_expired_batches` (boolean, default `false`)

## Forecasting

### `POST /api/forecast`

Generates a 7-day forecast using the real aiml forecasting engine.

Request body:
- `origin_date` (ISO-8601 date)
- `horizon_days` (integer, default `7`)
- `dataset_path` (string, optional)
- `use_cache` (boolean, default `true`)

## Planning

### `POST /api/plan`

Runs a single-cycle optimization and verification pass.

Request body:
- `origin_date` (ISO-8601 date)
- `horizon_days` (integer, default `7`)
- `lane_pruning_k` (integer, default `3`)
- `dataset_path` (string, optional)
- `cost_parameters` (object, optional)

## Risk overview

### `GET /api/risk`

Returns ranked risk alerts and network-level shortage diagnostics.

Query parameters:
- `origin_date` (required ISO-8601 date)
- `dataset_path` (optional string)
- `run_id` (optional string)

## Backtesting

### `POST /api/backtest`

Runs multi-cycle policy comparison.

## Runs

### `GET /api/runs`

Returns persisted planning / backtest runs.

### `GET /api/runs/{run_id}/network`

Returns map-ready location metadata, inventory and persisted pre-plan destination risk summaries,
and shipment allocations from the specified stored planning run. The response
includes both `run_id` and `dataset_hash`; the backend resolves the source
dataset by the run's recorded hash and rejects unavailable or changed datasets.
Coordinates are returned only when the matching warehouse or destination row
contains valid latitude and longitude values. Missing and invalid coordinates
are marked and are not inferred.
