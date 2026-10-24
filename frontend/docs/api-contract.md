# Frontend–Backend API Contract

The FastAPI application is the source of truth for endpoint and schema details.
Start the backend and open `http://localhost:8000/api/docs` for the generated
OpenAPI reference.

## Base URL

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

Do not include a trailing slash. The frontend uses `/api`, not `/api/v1`.
Requests are synchronous. Planning and backtest requests have extended client
timeouts because they run the corresponding engine before returning.

## Endpoints used by the frontend

| Purpose | Method and path | Request / query |
| --- | --- | --- |
| Health check | `GET /health` | None |
| Ensure demo data exists | `GET /demo-data` | `seed` (defaults to 42) |
| Validate planning data | `POST /data/validate` | `planning_date`; optional `dataset_path`, `exclude_expired_batches` |
| Forecast demand | `POST /forecast` | `origin_date`, `horizon_days` (1–28); optional `dataset_path`, `use_cache` |
| Assess inventory risk | `GET /risk` | `origin_date`; optional `dataset_path`, `run_id` |
| Generate a dispatch plan | `POST /plan` | `origin_date`, `horizon_days` (1–28), optional solver parameters |
| List stored runs | `GET /runs` | None |
| Retrieve run manifest | `GET /runs/{run_id}` | None |
| Export a run artifact | `GET /runs/{run_id}/export` | `format=csv|json`, `artifact=plan|risks|kpis` |
| Run policy evaluation | `POST /backtest` | `seed`, `window_days` (7–112); optional `evaluation_start_date`, `dataset_path` |

Before domain requests, the frontend calls `GET /demo-data` to create or load
the selected deterministic synthetic dataset. It then sends the API-specific
date and parameter names listed above.

## Response and error handling

- The frontend maps backend snake_case models into the view models used by the
  React pages. The adapters are in `src/services/`.
- The backend emits RFC 7807-style problem responses for domain errors. The API
  client accepts both `application/problem+json` and `application/json` and
  raises an `ApiError` with HTTP status, backend error code, and message.
- Run exports are returned by the backend as CSV or JSON content. CSV
  neutralization is performed server-side.
- Risk results do not include regional labels or numeric network deficits.
  Backtest results contain aggregate K1–K7 comparisons and K8 decomposition,
  not daily trajectories. The UI does not synthesize those missing values.

## AI/ML ownership

The HTTP API invokes the forecasting, optimization, and verification engines
in `backend/backend/engines/`. The separate top-level `aiml/` Python package
provides an offline research/demo workflow and is not currently deployed as a
service or imported by the FastAPI application.
