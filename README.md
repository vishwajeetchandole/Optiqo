# Optiqo

Optiqo is an AI-powered distribution intelligence and inventory optimization platform for FMCG and distribution teams. It combines demand forecasting, risk analysis, allocation planning, and simulation-backed evaluation into a single workflow.

## Architecture

- `frontend/` — React + Vite + Tailwind dashboard and user flows
- `backend/` — FastAPI REST API, validation, orchestration, simulation, and persistence
- `aiml/` — forecasting, optimization, verification, benchmarking, and evaluation logic
- `docs/` — shared API contract and data schema documentation

The intended runtime flow is:

React frontend -> FastAPI API -> validation/orchestration -> demo data / dataset pipeline -> forecasting and optimization -> risk and backtest evaluation -> UI response

## Quick start

The frontend uses the FastAPI backend for its data. Start the backend and
frontend in separate terminals.

### 1) Backend

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal running. The API health check is available at
`http://localhost:8000/api/health`.

### 2) Frontend
```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

The default frontend config calls `http://localhost:8000/api` with mock
responses disabled. If the backend is unreachable, check that its terminal is
still running and that `VITE_API_BASE_URL` points to the correct API.

### 3) AI/ML module

```powershell
cd aiml
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests -q
```

## API health check

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

## Key API routes

- `GET /api/health`
- `GET /api/demo-data`
- `POST /api/data/validate`
- `POST /api/forecast`
- `POST /api/plan`
- `GET /api/risk`
- `POST /api/backtest`
- `GET /api/runs`

## Notes

- Use synthetic demo data unless a real dataset is intentionally loaded.
- The app is a decision-support tool; it does not execute warehouse actions.
- Data validation, solver feasibility, and independent verification are treated as required gates before recommendations are shown.
