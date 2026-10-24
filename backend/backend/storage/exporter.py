"""
Optiqo — Sanitized CSV & JSON Artifact Exporter (PRD §5.1 P0-11, §14 N8, Plan §4.9)

Features:
- Formula injection neutralization: prepends single quote `'` to any string cell beginning with `=`, `+`, `-`, `@`, `\t`, `\r`.
- Artifact serializations for:
  • "plan": planned shipment lines with allocations, destinations, and verified explanations.
  • "risks": inventory and supply risk alerts, financial exposure, and shortage flags.
  • "kpis": comparative K1–K8 business metrics, gain decomposition, and calibration scores.
- Dual format support: "csv" (streamed text/csv) and "json" (structured application/json).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any
import pandas as pd

from backend.core.exceptions import DataError
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Trigger characters capable of formula execution in spreadsheet software (PRD §14 N8)
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> Any:
    """
    Neutralize CSV formula injection by prepending a single quote `'`
    if a string cell begins with =, +, -, @, \\t, or \\r (PRD §14 N8).
    Genuine numeric values (including negative numbers) are preserved as numeric values.
    """
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value

    s = str(value)
    if not s:
        return s

    # Preserve genuine numeric values even if formatted as strings (e.g. "-15.2", "-5")
    try:
        float(s)
        return value
    except ValueError:
        pass

    if s[0] in FORMULA_TRIGGERS:
        # Prepend single quote to neutralize formula execution in Excel/Sheets
        return f"'{s}"
    return s


def sanitize_dataframe_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Apply formula injection neutralization to all cells of a DataFrame."""
    clean_df = df.copy()
    for col in clean_df.columns:
        clean_df[col] = clean_df[col].apply(sanitize_csv_cell)
    return clean_df


def dataframe_to_sanitized_csv(df: pd.DataFrame) -> str:
    """Convert DataFrame to sanitized CSV string with quotechar and neutralization."""
    clean_df = sanitize_dataframe_for_csv(df)
    buf = io.StringIO()
    clean_df.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL)
    return buf.getvalue()


def export_run_artifact(
    run_data: dict[str, Any],
    artifact: str,
    export_format: str = "csv",
    format: str | None = None,
) -> tuple[str, str]:
    """
    Export requested artifact from run_data in specified format.
    Returns (content_str, media_type).
    Raises DataError (HTTP 422) if artifact or format is invalid.
    """
    effective_format = format if format is not None else export_format
    fmt_lower = effective_format.strip().lower()
    art_lower = artifact.strip().lower()

    if fmt_lower not in ("csv", "json"):
        raise DataError(
            message=f"Unsupported export format: '{export_format}'. Supported formats: 'csv', 'json'."
        )

    if art_lower not in ("plan", "risks", "kpis"):
        raise DataError(
            message=f"Unsupported artifact: '{artifact}'. Supported artifacts: 'plan', 'risks', 'kpis'."
        )

    # 1. Plan Artifact
    if art_lower == "plan":
        plan_lines = run_data.get("plan_lines") or []
        if fmt_lower == "json":
            content = json.dumps(
                {
                    "run_id": run_data.get("run_id"),
                    "origin_date": run_data.get("origin_date"),
                    "status": run_data.get("status"),
                    "summary": run_data.get("summary"),
                    "plan_lines": plan_lines,
                },
                indent=2,
                default=str,
            )
            return content, "application/json"

        # CSV format
        rows = []
        for line in plan_lines:
            explanation = line.get("explanation", {})
            rows.append({
                "line_id": line.get("line_id", ""),
                "warehouse_id": line.get("warehouse_id", ""),
                "batch_id": line.get("batch_id", ""),
                "sku_id": line.get("sku_id", ""),
                "dest_id": line.get("dest_id", ""),
                "quantity": line.get("quantity", 0),
                "arrival_date": line.get("arrival_date", ""),
                "total_freight_cost": line.get("total_freight_cost", 0.0),
                "explanation_sentence": explanation.get("sentence", "") if isinstance(explanation, dict) else str(explanation),
                "next_best_warehouse": explanation.get("evidence", {}).get("next_best_warehouse") if isinstance(explanation, dict) else "",
            })

        df = pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["line_id", "warehouse_id", "batch_id", "sku_id", "dest_id", "quantity", "arrival_date", "total_freight_cost", "explanation_sentence"]
        )
        return dataframe_to_sanitized_csv(df), "text/csv"

    # 2. Risks Artifact
    elif art_lower == "risks":
        # Check if pre_plan risk or summary alerts exist
        summary = run_data.get("summary") or {}
        risk_data = run_data.get("risk_alerts") or []

        if fmt_lower == "json":
            content = json.dumps(
                {
                    "run_id": run_data.get("run_id"),
                    "summary": summary,
                    "risk_alerts": risk_data,
                },
                indent=2,
                default=str,
            )
            return content, "application/json"

        # CSV format
        if risk_data:
            df = pd.DataFrame(risk_data)
        else:
            # Flatten summary risk metrics into tabular rows
            rows = [
                {"metric": "expected_unmet_demand_before", "value": summary.get("expected_unmet_demand_before", 0.0)},
                {"metric": "expected_unmet_demand_after", "value": summary.get("expected_unmet_demand_after", 0.0)},
                {"metric": "expected_expiry_loss_before", "value": summary.get("expected_expiry_loss_before", 0.0)},
                {"metric": "expected_expiry_loss_after", "value": summary.get("expected_expiry_loss_after", 0.0)},
                {"metric": "supply_bound_unavoidable_shortage", "value": summary.get("supply_bound_unavoidable_shortage", 0.0)},
                {"metric": "allocation_caused_shortage", "value": summary.get("allocation_caused_shortage", 0.0)},
            ]
            df = pd.DataFrame(rows)

        return dataframe_to_sanitized_csv(df), "text/csv"

    # 3. KPIs Artifact
    else:  # kpis
        kpi_data = run_data.get("kpi_comparison") or run_data.get("summary") or {}
        forecast_kpis = run_data.get("forecast_kpis") or {}
        optimization_kpis = run_data.get("optimization_kpis") or {}

        if fmt_lower == "json":
            content = json.dumps(
                {
                    "run_id": run_data.get("run_id"),
                    "kpi_comparison": kpi_data,
                    "forecast_kpis": forecast_kpis,
                    "optimization_kpis": optimization_kpis,
                },
                indent=2,
                default=str,
            )
            return content, "application/json"

        # CSV format
        rows = []
        if isinstance(kpi_data, dict):
            for k, v in kpi_data.items():
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        rows.append({"kpi_group": k, "metric": sub_k, "value": sub_v})
                else:
                    rows.append({"kpi_group": "summary", "metric": k, "value": v})

        if isinstance(forecast_kpis, dict):
            for k, v in forecast_kpis.items():
                rows.append({"kpi_group": "forecast_kpi", "metric": k, "value": v})

        if isinstance(optimization_kpis, dict):
            for k, v in optimization_kpis.items():
                rows.append({"kpi_group": "optimization_kpi", "metric": k, "value": v})

        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["kpi_group", "metric", "value"])
        return dataframe_to_sanitized_csv(df), "text/csv"
