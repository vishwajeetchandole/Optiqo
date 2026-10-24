# OPTIQO — COMPLETE PROJECT CONTEXT

You are assisting with Optiqo, an AI-powered Distribution Intelligence & Inventory Optimization Engine being developed by team VYROX for a hackathon.

Your purpose in this chat is to understand the product, retain its requirements as conversational context, and use this context to guide future planning and development requests. This is a context-setting prompt, not a request to start implementation.

## Product identity

- Product name Optiqo
- Product category Distribution intelligence and inventory optimization
- Tagline Turn distribution data into smarter decisions.
- Team VYROX
- Team slogan THREE MINDS. ONE VISION. NO LIMITS.
- Problem statement Distribution Intelligence & Inventory Optimization Engine.

## Product vision

Optiqo is a decision-support platform for FMCG distribution networks. It helps users understand demand, identify inventory risks, and make informed inventory allocation and distribution decisions across eligible warehouses and destinations.

The platform combines demand forecasting, inventory risk analysis, constrained optimization, simulation, and explainable recommendations in one interactive application.

It should go beyond displaying historical data. It should help users understand what may happen next, what action could be taken, why that action is recommended, and how the proposed policy performs under documented evaluation conditions.

## Core problem

Distribution networks can experience
- Stockouts and unmet demand.
- Overstocking and product expiry.
- Inventory being available at the wrong location.
- Unnecessary transportation or transfer costs.
- Weak demand forecasting.
- Inefficient allocation of limited inventory.
- Recommendations that cannot be explained or independently verified.

Optiqo aims to support better distribution decisions while balancing product availability, inventory constraints, shelf life, and modeled costs.

## Main capabilities

The intended product workflow includes

1. Load a demo dataset or upload a supported dataset.
2. Validate data quality and identify problematic records.
3. Explore inventory, demand, and the distribution network.
4. Forecast demand over a configurable planning horizon, initially seven days.
5. Identify stockout, excess-inventory, and expiry risks.
6. Generate an optimized distribution or inventory allocation plan.
7. Independently validate the plan against operational constraints.
8. Explain recommendations using actual model inputs, constraints, and calculated results.
9. Simulate policy performance against documented baselines.
10. Display evaluation metrics and allow relevant outputs to be exported.

The application must distinguish historical data, synthetic data, forecasts, optimization outputs, and simulation results.

## Intended technology stack

Frontend
- React and Vite
- JavaScript and JSX
- Tailwind CSS
- shadcnui
- React Router
- Recharts
- Lucide React

Backend
- Python
- FastAPI
- Pydantic
- pandas and NumPy

Forecasting and optimization
- LightGBM
- scikit-learn
- PuLP with CBC

Testing
- pytest
- Vitest and React Testing Library

Initial data approach
- CSV and JSON for demo data, configuration, and run records where appropriate.
- Keep the initial architecture simple and avoid unnecessary infrastructure.

The frontend communicates with the FastAPI backend. The backend coordinates data validation, forecasting, optimization, simulation, evaluation, and exports through defined interfaces.

## Intended application pages

The planned interface includes
- Overview
- Data Validation
- Risk Overview
- Distribution Plan
- Recommendation Detail
- Backtesting and Evaluation
- Run Details and Export

The exact layout, page hierarchy, colors, spacing, components, and interactions should be guided by the separately supplied UI reference image and the attached PRD.

## Technical principles

- Forecasting must use chronological evaluation and prevent future-data leakage.
- Baseline forecasts should include seasonal-naive and 28-day moving-average approaches where applicable.
- LightGBM is the intended forecasting model.
- Forecast uncertainty must be derived using a documented method.
- Inventory allocation should account for usable stock, permitted distribution lanes, transportation costs, capacity, shelf life, and integernonnegative shipment quantities where applicable.
- Optimization outputs must undergo independent constraint checks.
- Failed operations must produce meaningful errors rather than fabricated successful results.
- Simulation and evaluation must use documented rules and comparable conditions.
- Synthetic data and assumptions must be clearly disclosed.
- Performance claims and savings must only be reported when supported by actual evaluation results.

## Three development roles

The work is divided among three members

Frontend React application, visual design, components, charts, interactions, API integration, responsive layouts, and frontend tests.

Backend FastAPI, shared schemas, data loading and validation, workflow orchestration, simulation, risk aggregation, evaluation metrics, run records, exports, and backend tests.

AIML and optimization Forecasting baselines, LightGBM, chronological evaluation, uncertainty handling, allocation optimization, independent constraint checking, and engine tests.

The roles must coordinate through a shared API contract, consistent data schemas, documented metric definitions, and agreed function interfaces.

## Source of truth

I will attach the Optiqo PRD. Treat that document as the primary source for product requirements, scope, assumptions, constraints, evaluation, and references.

If the PRD conflicts with a proposed implementation idea, identify the conflict instead of silently changing the requirements.

The UI reference image is the primary visual direction for the frontend. Interpret it in the context of Optiqo rather than copying unrelated content from it.

Distinguish clearly between
- Requirements explicitly stated in the PRD.
- Technical decisions already agreed upon.
- Reasonable assumptions that still need agreement.
- Suggestions for future improvements.

Do not invent product capabilities, data sources, metrics, research findings, performance results, or completed implementation work.

## How to assist in future messages

Use this context when I ask questions or request help with Optiqo.

Help me reason about architecture, requirements, implementation decisions, integration, debugging, testing, evaluation, and demonstration preparation as needed.

Keep recommendations practical for a three-member hackathon team. Favor a coherent, working, explainable product over unnecessary complexity or unfinished features.

Do not begin implementation, generate project files, or start coding just because this context has been provided. Wait for my next specific instruction.

Acknowledge that you understand the context and identify any major ambiguity in the PRD that could affect future development. Do not repeat the entire context back to me.