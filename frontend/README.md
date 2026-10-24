# StockWise AI (Optiqo) — Frontend

> **VYROX SGU HACKATHON**  
> StockWise AI is a decision-support system for FMCG supply chains. It targets Supply Chain Managers, Demand Planners, and Warehouse Managers who struggle with uneven stock levels, stockouts, and high transport costs.

This repository branch (`front`) contains the React + Vite frontend for Optiqo / StockWise AI.

---

## 🚀 Quickstart & Setup

### Prerequisites
- Node.js >= 18.0.0
- npm >= 9.0.0

### Installation & Run
```bash
# Install dependencies
npm install

# Start local development server
npm run dev

# Run unit / integration tests
npm run test

# Build for production
npm run build

# Run linter
npm run lint
```

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env.local` to configure:

```env
# Base URL for the backend REST API
VITE_API_BASE_URL=http://localhost:8000/api

# Set to true only when intentionally using the local mock adapters
VITE_USE_MOCKS=false
```

---

## 🗺️ Key Features & Routes

- **Dashboard (`/`)**: Current run summaries, backend demand forecasts, risk distribution, and alerts.
- **Data Pre-flight Validation (`/validation`)**: Automated checks, input data sanity checks, and issue inspection drawer.
- **Network Risk Analysis (`/risk`)**: Backend-ranked SKU-destination risks and reported exposure details.
- **Distribution Plan (`/plan`, `/plan/:lineId`)**: Backend-generated transfer recommendations, verification results, line evidence, and sanitized CSV export.
- **Historical Backtesting (`/backtest`)**: Backend K1–K7 comparisons and K8 cost decomposition. Daily trajectories are not part of the current API contract.
- **Solver Run Inspector (`/runs`)**: Persisted execution runs, run comparisons, plan CSV exports, and JSON manifests.

The FastAPI backend serves the HTTP API consumed by this frontend. Its forecasting,
optimization, and verification implementations live in `backend/backend/engines`.
The top-level `aiml/` package is a separate offline research/demo toolkit; it is
not currently loaded as a remote service by the backend.
