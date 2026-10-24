# Optiqo data schema

This project uses a deterministic synthetic demo dataset generated into `backend/data/demo_data/seed_<n>/`.

## Core dataset tables

- `skus.csv`
- `warehouses.csv`
- `destinations.csv`
- `lanes.csv`
- `inventory.csv`
- `demand.csv`
- `sales_daily.csv`
- `calendar_events.csv`
- `capacity.csv`
- `config.csv`

## Common conventions

- Dates are ISO-8601 (`YYYY-MM-DD`).
- Quantities are non-negative integers or floats where applicable.
- Product identifiers and warehouse/destination IDs are string keys used across tables.
- Shelf life and expiry values are measured in days.
- Cost values are modeled as numeric amounts aligned to the optimization objective.

## Validation rules

- No duplicate identifiers across the relevant tables.
- Dates must be chronological and within the supported planning window.
- Inventory, demand, capacity, and transfer values must not be negative.
- Route eligibility and product compatibility must be codified in the lane and inventory tables.
- Expired batches are rejected or excluded according to planning_date rules.

These rules are checked by the backend validation pipeline and enforced before planning or risk calculation begins.
