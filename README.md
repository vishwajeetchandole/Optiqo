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

### 1) Frontend

```powershell
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The default frontend env is configured for the local backend at `http://localhost:8000/api` with mock responses disabled by default.

### 2) Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "C:\Users\vishw\Downloads\Optiqo"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

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
