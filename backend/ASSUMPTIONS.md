# OPTIQO — ARCHITECTURAL ASSUMPTIONS & REQUIREMENTS SPECIFICATION
**Document Version:** 1.0  
**Project:** Optiqo — AI-Powered Distribution Intelligence & Inventory Optimization Engine  
**Team:** VYROX  
**Role:** Senior Backend Architect  

---

## 1. Document Overview & Classification Framework

To ensure flawless coordination between the **Backend**, **Frontend (React)**, and **AI/ML & Optimization** workstreams, this document provides a rigorous, source-grounded breakdown of all project requirements, architectural proposals, unresolved questions, and operational assumptions.

All items are categorized into four distinct classes:
- **Class A: Confirmed Requirements** — Directly established from [master_context.md](file:///r:/Optiqo/master_context.md), [Optiqo_PRD.md](file:///r:/Optiqo/Optiqo_PRD.md), and [backend.md](file:///r:/Optiqo/backend.md).
- **Class B: Proposed Technical Decisions** — Architectural solutions proposed by the backend architect to fulfill Class A requirements efficiently.
- **Class C: Unresolved Questions & Ambiguities** — Design decisions requiring explicit stakeholder agreement before implementation starts.
- **Class D: Operational & Modeling Assumptions** — Domain and supply-chain simplifications inherent to the optimization and simulation models.

---

## 2. Class A: Confirmed Requirements (Source-Grounded)

### 2.1 Dataset Structure & Relationships (PRD §11.1)
The data layer is defined by 10 specific tables. All foreign keys must be strictly enforced.

1. **`skus`** (`sku_id` PK): `name`, `category`, `shelf_life_days`, `min_life_days`, `unit_volume`, `unit_cost`, `unit_margin` (Optional: `case_size`).
2. **`warehouses`** (`warehouse_id` PK): `name`, `region` (Optional: `capacity`).
3. **`destinations`** (`dest_id` PK): `name`, `type` (distributor/store), `region`, `storage_capacity` (Optional: `size tier`).
4. **`lanes`** (`warehouse_id`, `dest_id` Composite PK): `distance_km`, `transit_days`, `freight_rate` (Optional: `blocked`, `truck_capacity`, `truck_fixed_cost`).
5. **`sales_daily`** (`date`, `dest_id`, `sku_id` Composite PK): `units_sold` (Optional: `price`, `promo_flag`).
6. **`inventory_batches`** (`location_id`, `sku_id`, `batch_id` Composite PK): `location_type` (warehouse/destination), `quantity`, `expiry_date` (Optional: `received_date`).
7. **`inbound_shipments`** (`shipment_id` PK): `dest_id`, `sku_id`, `batch_id`, `quantity`, `arrival_date`, `expiry_date`.
8. **`warehouse_receipts`** (`receipt_id` PK): `warehouse_id`, `sku_id`, `batch_id`, `quantity`, `arrival_date`, `expiry_date`.
9. **`calendar_events`** (`date` PK): `festival_flag`, promotion flags by SKU/category (Optional: `weather index`).
10. **`config`** (Singleton/Key-Value): `shortage penalty factor`, `holding cost rate`, `horizon`, `baseline safety days` (Optional: `scenario weights`).

*Entity Relationships:*
- `lanes`, `inventory_batches` (location_type='warehouse'), `warehouse_receipts` $\rightarrow$ `warehouses.warehouse_id`.
- `lanes`, `inventory_batches` (location_type='destination'), `inbound_shipments`, `sales_daily` $\rightarrow$ `destinations.dest_id`.
- `inventory_batches`, `inbound_shipments`, `warehouse_receipts`, `sales_daily` $\rightarrow$ `skus.sku_id`.

### 2.2 Data Validation & 13 Fault Types (PRD §5.1 P0-02, §11.2, §16.1 E6)
Planning is strictly blocked if any of the following 13 fault types are detected:
1. **Missing required file** (any of the 10 core tables absent).
2. **Missing required column** (mandatory schema column absent).
3. **Missing required value** (null, empty string, or NaN in a mandatory column).
4. **Non-numeric or negative quantity** (quantity $< 0$ or non-numeric type).
5. **Invalid or unparsable date format** (dates not conforming to standard ISO-8601 YYYY-MM-DD).
6. **Duplicate primary key** (duplicate keys in entity tables).
7. **Unknown SKU identifier** (foreign key reference to nonexistent SKU).
8. **Unknown warehouse identifier** (foreign key reference to nonexistent warehouse).
9. **Unknown destination identifier** (foreign key reference to nonexistent destination).
10. **Expired batch** (batch expiry date $\le$ current planning date $t_0$).
11. **Non-positive storage capacity** (storage capacity $\le 0$ in destinations).
12. **Non-positive unit volume** (unit volume $\le 0$ in skus).
13. **Transit days below 1** (transit days $< 1$ in lanes).

*Warnings (Planning Allowed):*
- Gaps in historical sales days (filled with median of last 4 same-weekdays).
- Extreme demand outliers.
- Destination starting stock exceeding physical storage capacity.

### 2.3 Usable Inventory & Shelf-Life Calculation (PRD §5.1 P0-03, §8.2, §10.2)
- For every warehouse batch $b$ and destination $l$:
  - Arrival date: $t_{\text{arr}} = t_0 + \tau(w(b), l)$.
  - Remaining shelf life at arrival: $r(b, l) = e_b - t_{\text{arr}}$.
  - Batch eligibility rule (Hard Constraint C2): $r(b, l) \ge m_{s(b)}$ (where $m_s$ is `skus.min_life_days`), lane is not blocked, and batch stock $Q_b > 0$.
  - Total on-hand warehouse inventory must exactly equal $\text{Usable Stock} + \text{Unusable Stock}$.

### 2.4 Demand Forecasting & Calibration (PRD §5.1 P0-04, §10.4)
- **Horizon:** Daily forecast for days $t_0+1$ through $t_0+7$ ($H=7$).
- **Leakage Prevention:** No features may use sales data occurring after $t_0$. Target date features lag $\ge 7$ days relative to target date.
- **Candidate Models:** Seasonal-Naive, 28-day Moving Average, and LightGBM with Tweedie objective.
- **Selection Rule:** Per forecast group (category $\times$ volume tier), pick the method with lowest validation weekly WAPE on days 281–364.
- **Demand Multipliers:** Low ($\mu_{\text{low}}$), Mid ($\mu_{\text{mid}}$), High ($\mu_{\text{high}}$) from 10th, 50th, and 90th empirical percentiles of the validation residuals.
- **Scenario Weights:** Default $\pi = (0.3, 0.4, 0.3)$ with outer-weight diagnostic adjustment.
- **Automated Fallbacks:**
  - $< 56$ days history: Category/region weekday profile $\times$ destination size factor.
  - LightGBM error: Better of Seasonal-Naive and 28-day MA.
  - LightGBM validation WAPE $\ge$ baseline: Baseline chosen.
  - Negative forecast: Clipped to zero.

### 2.5 Allocation Optimization Formulation (PRD §5.1 P0-05, §10.2, §10.3, §10.5)
- Continuous Linear Program solved via PuLP and CBC solver, post-processed with conservative integer round-down (C4).
- **Decision Variable:** $x(b, l) \ge 0$, whole units shipped from batch $b$ to destination $l$.
- **Objective Function:** Minimize Total Modeled Cost:
  $$\min \sum_{(b,l) \in \text{Eligible}} \text{freight}(w(b), l) \cdot \text{vol}(s(b)) \cdot x(b, l) + \sum_{(l,s,k)} \pi_k \left( p_s \cdot \text{short}(l, s, k) + v_s \cdot \text{waste}(l, s, k) + h_s \cdot \text{end}(l, s, k) \right)$$
- **Penalties:** Soft penalties: $p_s = 1.5 \times \text{unit\_margin}_s$, $v_s = \text{unit\_cost}_s$, $h_s = 0.02 \times \text{unit\_cost}_s$.
- **Hard Constraints:**
  - C1: Batch stock availability ($\sum_l x(b, l) \le Q_b$).
  - C2: Lane and shelf-life eligibility ($r(b, l) \ge m_s$ and lane unblocked).
  - C3: Destination storage capacity ($\sum_s \text{vol}_s \sum_{b \in s} x(b, l) \le \text{capRoom}(l)$).
  - C4: Non-negative whole integers ($x(b, l) \in \mathbb{Z}_{\ge 0}$).
  - C5: Lane pruning (max 3 lowest-freight warehouses per $(l, s)$).

### 2.6 Independent Constraint Verification (PRD §5.1 P0-06, §7.4 O1)
- Verifier operates completely outside PuLP/CBC.
- Validates the final rounded integer allocation against C1–C5.
- If any violation is found, the plan is rejected and a failure status (`CHECK_FAILED`) is returned. No invalid plan is ever presented as final. Target: O1 = 0.

### 2.7 Recommendation Explanations & Evidence (PRD §5.1 P0-08, §10.9, §7.4 O3)
- Every plan line must contain an evidence dictionary and a deterministic template sentence.
- Evidence fields: forecast mean/range, current stock, inbound stock, shipped quantity, arrival shelf life vs. minimum, freight cost of chosen vs. next-best warehouse, batch saturation flag, capacity binding flag, unmet/waste delta.
- Verifier recomputes all numbers in the explanation from raw tables; mismatch target = 0 (O3 = 100%).

### 2.8 Baseline Policies & Gain Decomposition (PRD §5.1 P0-09, §10.7, §7.2 K8)
- **Baseline 1 (B1):** Target stock = 7-day trailing average $\times (7 + 2 \text{ safety days})$. Allocation: nearest warehouse with eligible stock, FEFO, proportional cut-back when short.
- **Baseline 2 (B2):** Same allocation as B1, but target stock uses Optiqo's mid-scenario forecast.
- **Optiqo:** Forecast-driven joint LP optimization.
- **Gain Decomposition:**
  $$\text{Forecast Effect} = \text{KPI}(B2) - \text{KPI}(B1)$$
  $$\text{Allocation Effect} = \text{KPI}(\text{Optiqo}) - \text{KPI}(B2)$$

### 2.9 Simulation Replay Engine (PRD §10.8, §7.1)
- 56-day evaluation window (days 365–420, 8 weekly dispatch cycles).
- Daily simulation order: (1) Receipts $\rightarrow$ (2) Expiry $\rightarrow$ (3) Sales $\rightarrow$ (4) Dispatch (weekly) $\rightarrow$ (5) Accounting.

### 2.10 KPI Evaluation Suite (PRD §7)
- **Business KPIs:** K1 (Unmet demand rate, $\ge 30\%$ red vs B1), K2 (Fill rate $\ge 95\%$), K3 (Stockout days $\ge 25\%$ red vs B1), K4 (Expiry wastage $\ge 40\%$ red vs B1), K5 (Freight per unit $\ge 10\%$ red vs B1), K6 (Total modeled cost $\ge 15\%$ red vs B1), K7 (Ending inventory $\le 10\%$ above B1), K8 (Gain decomposition).
- **Forecast KPIs:** F1 (Daily WAPE), F2 (Weekly WAPE), F3 (MAE), F4 (Bias $\le 5\%$), F5 (Coverage 70%–90%).
- **Optimization & System KPIs:** O1 (Violations = 0), O2 (Feasible rate = 100%), O3 (Grounded explanations = 100%), O4 (p95 runtime $\le 60\text{ s}$), O5 (Supply-bound shortage), S1 (E2E runtime $\le 120\text{ s}$), S2 (Reproducibility), S3 (Validation accuracy = 100%), S4 (Graceful failure = 100%).

---

## 3. Class B: Proposed Technical Decisions

### 3.1 Backend Technology & Service Separation
- **Web Framework:** FastAPI with Uvicorn.
- **Data Validation:** Pydantic v2 schemas for all payloads and domain transfers.
- **Data Manipulation:** pandas and NumPy.
- **Optimization Engine:** PuLP with the open-source COIN-OR CBC solver.
- **Forecasting:** LightGBM regressor with scikit-learn preprocessing.

### 3.2 Storage & Run Management (Lightweight Architecture)
- In accordance with `master_context.md` ("keep the initial architecture simple and avoid unnecessary infrastructure"):
  - No external SQL/NoSQL database server will be introduced for MVP.
  - Run records, manifests, and plan tables will be stored on local filesystem under `storage/runs/{run_id}/` as JSON manifests and CSV plan tables.
  - Demo data resides in `data/demo_data/`.

### 3.3 Protocol-Based Engine Decoupling
- Forecasting, Optimization, and Independent Verification are defined as Python `typing.Protocol` classes.
- This allows the AI/ML workstream to develop and refine models in isolation while the backend uses reference implementations and mocks for testing.

### 3.4 CSV Formula Injection Neutralization (PRD §14 N8)
- Any CSV cell beginning with `=`, `+`, `-`, or `@` will be automatically prepended with a single quote (`'`) during export to prevent spreadsheet formula injection vulnerabilities.

### 3.5 Error Handling Standard
- All API exceptions map to RFC 7807 Problem Details JSON format:
  ```json
  {
    "type": "https://optiqo.vyrox.ai/errors/DATA_VALIDATION_FAILED",
    "title": "Data Validation Failed",
    "status": 422,
    "detail": "2 blocking errors detected in dataset.",
    "instance": "/api/data/validate",
    "code": "ERROR_DATA",
    "errors": [...]
  }
  ```

---

## 4. Class C: Unresolved Questions & Ambiguities (Decisions Requiring Agreement)

| ID | Issue / Question | Options Considered | Recommended Decision | Impact if Unresolved |
|---|---|---|---|---|
| **Q1** | **`GET /api/risk` Route Contract & State**<br>`backend.md` specifies `GET /api/risk`. Does it evaluate risk on the default dataset on-the-fly, or does it retrieve risk for a specific `run_id`? | Option A: Pure GET with query parameters `?origin_date=...&run_id=...`. If `run_id` given, fetch saved run; if not, compute pre-plan risk on current inventory.<br>Option B: Make it `POST /api/risk` accepting dataset/state. | **(Recommended) Option A:** Keep `GET /api/risk?origin_date=YYYY-MM-DD&run_id=...` to preserve `backend.md` spec while allowing pre-plan and post-plan risk views. | Frontend may pass unexpected parameters or expect static data. |
| **Q2** | **Demo Dataset Lifecycle & Generation**<br>Should the synthetic demo dataset be pre-generated and stored in git, or generated at backend bootstrap if missing? | Option A: Generator runs dynamically on startup if `data/demo_data/` is missing.<br>Option B: Static CSVs are pre-generated and committed into repository. | **(Recommended) Option A with caching:** Store generated CSVs in `data/demo_data/`. If missing, `synthetic_generator.py` seeds them immediately on startup or upon calling `GET /api/demo-data?reset=true`. | Potential cold-start delay or missing dataset files on clean checkout. |
| **Q3** | **Python Version & LightGBM/PuLP Wheel Compatibility**<br>The host system currently has Python 3.14.7 installed. Many scientific packages (LightGBM, scikit-learn, PuLP/CBC) frequently do not distribute pre-compiled Windows wheels for bleeding-edge Python versions. | Option A: Attempt installation on host Python 3.14.<br>Option B: Recommend/require a dedicated Python 3.11 virtual environment. | **(Recommended) Option B:** Use Python 3.11 for development, as specified in PRD §6.2. | C++ compilation failures during package installation on Windows. |
| **Q4** | **Execution Model for `/api/backtest`**<br>A 56-day simulation involving 8 full LP solves may take 15–40 seconds. Should the API call be synchronous or asynchronous? | Option A: Synchronous HTTP request with client-side timeout set to 60s.<br>Option B: Asynchronous task returning `task_id` with polling on `GET /api/tasks/{task_id}`. | **(Recommended) Option A for MVP:** Keep synchronous since runtime target S1 is $\le 120\text{ s}$ and backtest target is under 40s. Client timeout configured to 90s. | HTTP timeouts in frontend or proxy during backtest runs. |
| **Q5** | **Missing Values in Sales History (Zero vs Missing)**<br>In retail FMCG, an SKU not appearing on a date at a destination could mean 0 sales or a store closure. | Option A: Treat missing date records as 0 sales.<br>Option B: Require full cartesian product in `sales_daily.csv`. | **(Recommended) Option A:** In `loader.py`, unobserved SKU-destination-date tuples default to 0 units sold unless flagged as store closure. | Forecaster might perceive missing dates as fatal data corruption. |

---

## 5. Class D: Operational & Modeling Assumptions

1. **Exogenous Supply Receipts:** Warehouse replenishment shipments (`warehouse_receipts`) are exogenous and fixed across all policies. Upstream manufacturing, plant scheduling, and supplier ordering are outside system scope.
2. **Deterministic Transit Times:** Lead times between warehouses and destinations are deterministic integers between 1 and 3 days. No traffic or weather delays are modeled.
3. **Lost Sales (No Backordering):** Any customer demand not met on the day of occurrence is permanently lost. Unmet demand does not backlog to future days.
4. **No SKU Substitution:** Consumers do not substitute a stocked SKU for an out-of-stock SKU.
5. **Single-Echelon Distribution:** Goods flow strictly from warehouses to destinations. Destination-to-destination lateral transshipments are not permitted.
6. **Strict Destination FEFO:** Destinations sell inventory strictly First-Expired, First-Out.
7. **Planning Horizon Aggregation Approximation:** In the single-cycle LP formulation (PRD §10.3), stock is approximated as available across the 7-day horizon to maintain linear solvability, while the day-by-day simulator strictly models transit arrival lag. Any resulting optimism is captured and reported in KPI K1/K6.
8. **Cost Parameter Realism:** Penalty and cost parameters are reasonable industry approximations rather than audited financial accounting numbers.
