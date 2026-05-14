"""Supabase persistence helpers for the Streamlit app.

Wraps supabase-py with the small set of CRUD operations the app actually
needs. Returns plain dicts/lists; raises on errors so the caller can decide
whether to degrade gracefully.

Design notes:
- The Supabase client is created from Streamlit secrets at module import time
  via get_client() — cached for the session.
- All writes use the service_role key (RLS bypass for trusted internal app).
- Run and audit-log writes never block the UI flow; callers should wrap in
  try/except and continue if writes fail (graceful degradation).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from supabase import Client, create_client

import streamlit as st


# ----------------------------------------------------------------------
# Client construction
# ----------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_client() -> Optional[Client]:
    """Return a cached Supabase client, or None if secrets missing.

    Caller must handle None — Supabase features should silently disable.
    """
    try:
        url = st.secrets["supabase"]["url"]
        # Prefer service_key for write operations (RLS bypass).
        key = st.secrets["supabase"].get("service_key") or st.secrets["supabase"]["anon_key"]
        return create_client(url, key)
    except Exception:
        return None


def is_available() -> bool:
    return get_client() is not None


# ----------------------------------------------------------------------
# Segment registers
# ----------------------------------------------------------------------

def list_canonical_registers() -> List[Dict[str, Any]]:
    """Return all canonical segment registers (is_canonical=true)."""
    client = get_client()
    if client is None:
        return []
    res = (
        client.table("segment_registers")
        .select("id, name, estate, description, segment_count, total_envelope_kwp, source_reference")
        .eq("is_canonical", True)
        .order("estate")
        .execute()
    )
    return res.data or []


def load_register_csv(register_id: str) -> Optional[pd.DataFrame]:
    """Fetch full CSV content for a register id and return as DataFrame."""
    client = get_client()
    if client is None:
        return None
    res = (
        client.table("segment_registers")
        .select("csv_content")
        .eq("id", register_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    from io import StringIO
    return pd.read_csv(StringIO(res.data[0]["csv_content"]))


def save_register(
    name: str,
    estate: str,
    csv_content: str,
    uploaded_by_email: str,
    description: str = "",
    is_canonical: bool = False,
    source_reference: str = "",
) -> Optional[str]:
    """Insert a new segment register. Returns row id or None on failure."""
    from io import StringIO
    client = get_client()
    if client is None:
        return None
    df = pd.read_csv(StringIO(csv_content))
    # Total envelope: prefer kwp_dc; fall back to kwp; tolerate absent.
    total_kwp: Optional[float] = None
    if "kwp_dc" in df.columns:
        total_kwp = float(df["kwp_dc"].sum())
    elif "kwp" in df.columns:
        total_kwp = float(df["kwp"].sum())
    payload = {
        "name": name,
        "estate": estate,
        "description": description,
        "segment_count": len(df),
        "total_envelope_kwp": total_kwp,
        "csv_content": csv_content,
        "uploaded_by_email": uploaded_by_email,
        "is_canonical": is_canonical,
        "source_reference": source_reference,
    }
    res = client.table("segment_registers").insert(payload).execute()
    return res.data[0]["id"] if res.data else None


# ----------------------------------------------------------------------
# Runs
# ----------------------------------------------------------------------

def save_run(
    estate: str,
    inputs_snapshot: Dict[str, Any],
    results_snapshot: Dict[str, Any],
    cashflow_data: Optional[List[Dict]] = None,
    validation_report: Optional[Dict] = None,
    intake_warnings: Optional[List[str]] = None,
    intake_errors: Optional[List[str]] = None,
    engine_version: str = "1.1.0",
    param_version: str = "1.1.1",
    ran_by_email: str = "anonymous@dev",
    run_label: Optional[str] = None,
    segment_register_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[str]:
    """Persist a run. Returns row id or None on failure."""
    client = get_client()
    if client is None:
        return None
    payload = {
        "run_label": run_label,
        "estate": estate,
        "segment_register_id": segment_register_id,
        "inputs_snapshot": inputs_snapshot,
        "results_snapshot": results_snapshot,
        "cashflow_data": cashflow_data,
        "validation_report": validation_report,
        "intake_warnings": intake_warnings,
        "intake_errors": intake_errors,
        "engine_version": engine_version,
        "param_version": param_version,
        "ran_by_email": ran_by_email,
        "duration_ms": duration_ms,
    }
    res = client.table("runs").insert(payload).execute()
    return res.data[0]["id"] if res.data else None


def list_recent_runs(user_email: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List most recent runs, optionally filtered to a specific user."""
    client = get_client()
    if client is None:
        return []
    query = (
        client.table("runs")
        .select("id, run_label, estate, results_snapshot, engine_version, ran_by_email, ran_at")
        .order("ran_at", desc=True)
        .limit(limit)
    )
    if user_email:
        query = query.eq("ran_by_email", user_email)
    res = query.execute()
    return res.data or []


def load_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Load a single run with full inputs_snapshot for re-execution."""
    client = get_client()
    if client is None:
        return None
    res = client.table("runs").select("*").eq("id", run_id).limit(1).execute()
    return res.data[0] if res.data else None


# ----------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------

def log_audit(event_type: str, user_email: str, event_data: Optional[Dict] = None) -> None:
    """Best-effort audit log write. Silently swallows errors."""
    client = get_client()
    if client is None:
        return
    try:
        client.table("audit_log").insert({
            "event_type": event_type,
            "user_email": user_email,
            "event_data": event_data or {},
        }).execute()
    except Exception:
        # Never block the user flow on audit failures.
        pass


# ----------------------------------------------------------------------
# Result serialization helpers
# ----------------------------------------------------------------------

def financial_results_to_snapshot(fin) -> Dict[str, Any]:
    """Convert FinancialResults to a JSON-serializable dict for runs.results_snapshot."""
    return {
        "envelope_mwp": float(fin.envelope_mwp),
        "epc_usd_m": float(fin.epc_usd_m),
        "total_project_cost_usd_m": float(fin.total_project_cost_usd_m),
        "debt_usd_m": float(fin.debt_usd_m),
        "equity_usd_m": float(fin.equity_usd_m),
        "year1_revenue_usd_m": float(fin.year1_revenue_usd_m),
        "year1_opex_usd_m": float(fin.year1_opex_usd_m),
        "year1_ebitda_usd_m": float(fin.year1_ebitda_usd_m),
        "equity_irr": float(fin.equity_irr),
        "project_irr": float(fin.project_irr),
        "npv_at_discount_usd_m": float(fin.npv_at_discount_usd_m),
        "moic_y10": float(fin.moic_y10),
        "payback_years": float(fin.payback_years),
        "dscr_min": float(fin.dscr_min),
        "dscr_avg": float(fin.dscr_avg),
        "dscr_breach": bool(fin.dscr_breach),
        "y10_exit_irr": float(fin.y10_exit_irr),
    }


def cashflow_to_records(cashflow_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert cashflow DataFrame to JSON-serializable list of dicts."""
    return json.loads(cashflow_df.to_json(orient="records"))


def financial_inputs_to_snapshot(inputs) -> Dict[str, Any]:
    """Convert FinancialInputs dataclass to a JSON-serializable dict."""
    from dataclasses import asdict
    d = asdict(inputs)
    # Ensure JSON-serializable (no pandas/numpy types)
    return json.loads(json.dumps(d, default=str))


def validation_report_to_dict(report) -> Optional[Dict[str, Any]]:
    """Convert ValidationReport to a JSON-serializable dict."""
    if report is None:
        return None
    return {
        "is_lc": bool(report.is_lc),
        "all_passed": bool(report.all_passed),
        "summary": str(report.summary),
        "checks": [
            {
                "label": c.label,
                "expected": float(c.expected),
                "actual": float(c.actual),
                "passed": bool(c.passed),
            }
            for c in report.checks
        ],
    }
