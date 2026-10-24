# Optiqo Backend — Windows Launch Instructions

## Prerequisites

- Python 3.10 or newer
- Backend dependencies installed from `backend\requirements.txt`
- From the repository root, create a virtual environment if needed:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Run the backend

Open PowerShell in the repository root, then start the API:

```powershell
Set-Location .\backend
..\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at `http://localhost:8000`; interactive documentation is
at `http://localhost:8000/api/docs`.

## Quick health check

In another PowerShell terminal:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/health" | ConvertTo-Json -Depth 3
```

## Load the demo dataset

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/demo-data" | ConvertTo-Json -Depth 5
```

The frontend's local configuration should use
`VITE_API_BASE_URL=http://localhost:8000/api` and `VITE_USE_MOCKS=false`.

## Run backend tests

From the repository root:

```powershell
Set-Location .\backend
..\backend\.venv\Scripts\python.exe -m pytest -q
```

