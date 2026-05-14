"""
NewCo Investment Scoping Calculator – Streamlit UI
NC-STREAMLIT-001 v0.1
"""
import io
import time
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from engine.pipeline import run
from engine.financial import FinancialInputs
from engine import persistence, migrations

st.set_page_config(page_title="NewCo Scoping Calculator", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ---- T109: Auth gate (auth-aware mode; activates when [auth] secrets present) ----
def _auth_configured() -> bool:
    try:
        return bool(st.secrets.get("auth", {}).get("google", {}).get("client_id"))
    except Exception:
        return False

if _auth_configured():
    if not st.user.is_logged_in:
        st.title("NewCo Investment Scoping")
        st.write("Please log in with your authorized Google account.")
        st.button("Log in with Google", on_click=st.login, args=["google"])
        st.stop()
    current_user_email = st.user.email
else:
    current_user_email = "anonymous@dev"
# ----

st.title("NewCo Investment Scoping Calculator")
st.caption("v0.1 prototype · NC-METH-001 canonical pipeline · IEAT-Industrial only")

with st.sidebar:
    # Supabase status (T106 schema check + T107 connection)
    if persistence.is_available():
        client = persistence.get_client()
        schema_ok, schema_msg = migrations.apply_pending(client)
        if schema_ok:
            st.success(f"Supabase: {schema_msg}")
        else:
            st.warning(f"Supabase reachable but schema not ready: {schema_msg}")
    else:
        st.error("Supabase: not configured (check secrets)")

    st.header("Configuration")
    run_label = st.text_input("Run label (optional)", placeholder="e.g. LC v1.0 sponsor base")
    estate = st.selectbox("Estate", options=["Laem Chabang","Bangpoo","Bangplee","Map Ta Phut","Map Ta Phut Port","Lat Krabang","Lamphun","Other"], index=0)
    st.divider()
    st.subheader("Debt structure")
    ltv = st.slider("Debt LTV (%)", min_value=30, max_value=75, value=60, step=1)
    rate = st.number_input("Interest rate (%)", min_value=4.0, max_value=10.0, value=6.0, step=0.25)
    tenor = st.number_input("Tenor (years)", min_value=5, max_value=20, value=12, step=1)
    st.divider()
    st.subheader("Tariff override")
    tariff = st.number_input("PPA tariff (THB/kWh)", min_value=2.50, max_value=5.50, value=3.85, step=0.05)
    tariff_escalation = st.number_input("Tariff escalation (%/yr)", min_value=0.0, max_value=4.0, value=0.0, step=0.1)
    st.divider()
    st.subheader("BOI tax holiday")
    boi_years = st.selectbox("Tax holiday tenor", options=[8, 13], index=0)
    st.divider()
    st.caption(f"User: `{current_user_email}`")

col_upload, col_preset = st.columns([2, 1])
with col_upload:
    st.subheader("1. Upload segment CSV")
    uploaded = st.file_uploader("CSV with per-segment data", type=["csv"])
with col_preset:
    st.subheader("Or load a canonical preset")
    # T107: load canonical registers from Supabase if available; fall back to local files.
    canonical_registers = persistence.list_canonical_registers() if persistence.is_available() else []
    if canonical_registers:
        preset_options = ["None"] + [f"{r['name']} ({r['estate']})" for r in canonical_registers]
        preset_id_map = {f"{r['name']} ({r['estate']})": r["id"] for r in canonical_registers}
    else:
        preset_options = ["None", "LC v1.0 canonical (local fallback)"]
        preset_id_map = {}
    preset_choice = st.radio("Preset", preset_options, label_visibility="collapsed")

df_input = None
data_source = None
segment_register_id = None
if uploaded is not None:
    df_input = pd.read_csv(uploaded)
    data_source = f"Uploaded: {uploaded.name}"
    persistence.log_audit("register_uploaded", current_user_email, {"filename": uploaded.name, "rows": len(df_input)})
elif preset_choice != "None":
    if preset_choice in preset_id_map:
        # Load from Supabase
        segment_register_id = preset_id_map[preset_choice]
        df_input = persistence.load_register_csv(segment_register_id)
        if df_input is not None:
            data_source = f"Preset: {preset_choice}"
    else:
        # Local fallback
        preset_path = Path("data/lc_v1_segments.csv")
        if preset_path.exists():
            df_input = pd.read_csv(preset_path)
            data_source = f"Preset (local): {preset_choice}"
        else:
            st.warning(f"Preset file not found at {preset_path}")

if df_input is not None:
    st.success(f"Loaded: {data_source} · {len(df_input)} segments")
    with st.expander("Preview input data", expanded=False):
        st.dataframe(df_input.head(20), use_container_width=True)

st.divider()
run_button = st.button("Run scoping", type="primary", disabled=(df_input is None), use_container_width=True)

if run_button and df_input is not None:
    with st.spinner("Running pipeline (Stages 1-7)..."):
        _t0 = time.time()
        try:
            inputs = FinancialInputs(
                debt_ltv=ltv / 100,
                debt_rate=rate / 100,
                debt_tenor_years=int(tenor),
                tariff_thb_kwh=tariff,
                tariff_escalation=tariff_escalation / 100,
                boi_years=int(boi_years),
            )
            result = run(df_input, inputs=inputs)
        except Exception as e:
            persistence.log_audit(
                "pipeline_error",
                current_user_email,
                {"error_type": type(e).__name__, "error_message": str(e)[:200], "estate": estate},
            )
            st.error(f"Pipeline error: {e}")
            st.stop()
        _duration_ms = int((time.time() - _t0) * 1000)

    if result.intake_errors:
        st.error(f"Intake errors: {result.intake_errors}")
        st.stop()

    # T108: persist the run (best-effort; non-blocking on failure)
    try:
        run_id = persistence.save_run(
            estate=estate,
            inputs_snapshot=persistence.financial_inputs_to_snapshot(inputs),
            results_snapshot=persistence.financial_results_to_snapshot(result.financial_60_ltv),
            cashflow_data=persistence.cashflow_to_records(result.financial_60_ltv.cashflow_df),
            validation_report=persistence.validation_report_to_dict(result.validation_report),
            intake_warnings=result.intake_warnings,
            intake_errors=result.intake_errors,
            ran_by_email=current_user_email,
            run_label=run_label or None,
            segment_register_id=segment_register_id,
            duration_ms=_duration_ms,
        )
        if run_id:
            persistence.log_audit("run_created", current_user_email, {"run_id": run_id, "estate": estate})
            st.caption(f"Run saved: `{run_id[:8]}…`  ·  {_duration_ms} ms")
    except Exception as _e:
        st.caption(f"Run completed but not saved to DB: {type(_e).__name__}")

    fin = result.financial_60_ltv
    cf = fin.cashflow_df

    st.subheader("Headline metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total envelope", f"{fin.envelope_mwp:.2f} MWp", f"{len(result.df_validated)} segments")
    m2.metric("EPC", f"${fin.epc_usd_m:.2f}M")
    m3.metric("Total project cost", f"${fin.total_project_cost_usd_m:.2f}M")
    p50_mwh = float(result.df_yielded["p50_annual_kwh"].sum()) / 1000 if "p50_annual_kwh" in result.df_yielded.columns else 0
    m4.metric("P50 generation", f"{p50_mwh:,.0f} MWh/yr")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric(f"Equity IRR ({ltv}% LTV)", f"{fin.equity_irr*100:.1f}%")
    # DSCR: canonical IC headline is P90 minimum. P50 shown as delta for context.
    dscr_p90 = getattr(fin, "dscr_min_p90", 0.0) or 0.0
    dscr_label = "BREACH" if dscr_p90 < 1.05 else ("Lockup" if dscr_p90 < 1.15 else "OK")
    m6.metric(
        "DSCR min (P90)",
        f"{dscr_p90:.2f}x",
        delta=f"{dscr_label} · P50 {fin.dscr_min:.2f}x",
        delta_color="inverse" if dscr_p90 < 1.15 else "normal",
    )
    m7.metric("Payback (blended)", f"{fin.payback_years:.1f} yrs")
    m8.metric("Y10 exit IRR @13.5x", f"{fin.y10_exit_irr*100:.1f}%", f"MOIC {fin.moic_y10:.2f}x")

    st.divider()
    st.subheader("Annual cashflow (25 years)")
    fig = go.Figure()
    rev_col = "total_revenue_usd" if "total_revenue_usd" in cf.columns else "energy_revenue_usd"
    fig.add_trace(go.Scatter(x=cf["year"], y=cf[rev_col]/1e6, mode="lines", name="Revenue", line=dict(color="#1f77b4", width=2)))
    fig.add_trace(go.Scatter(x=cf["year"], y=cf["opex_usd"]/1e6, mode="lines", name="OPEX", line=dict(color="#64748B", width=2)))
    fig.add_trace(go.Scatter(x=cf["year"], y=cf["debt_service_usd"]/1e6, mode="lines", name="Debt service", line=dict(color="#F59E0B", width=2)))
    fig.add_trace(go.Scatter(x=cf["year"], y=cf["fcfe_usd"]/1e6, mode="lines", name="FCFE", line=dict(color="#0D9488", width=3), fill="tozeroy", fillcolor="rgba(13,148,136,0.1)"))
    fig.update_layout(xaxis_title="Year", yaxis_title="USD millions", hovermode="x unified", height=400, margin=dict(l=40,r=40,t=20,b=40))
    st.plotly_chart(fig, use_container_width=True)

    if result.tornado_results:
        st.divider()
        st.subheader("Sensitivity tornado (IRR +/- bps from base)")
        try:
            from engine.sensitivity import tornado_to_dataframe
            sens_df = tornado_to_dataframe(result.tornado_results).sort_values("Range (bps)", ascending=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(y=sens_df["Sensitivity"], x=sens_df["Upside (bps)"], name="Upside", orientation="h", marker_color="#0D9488"))
            fig2.add_trace(go.Bar(y=sens_df["Sensitivity"], x=sens_df["Downside (bps)"], name="Downside", orientation="h", marker_color="#F59E0B"))
            fig2.update_layout(barmode="overlay", xaxis_title="IRR delta (bps)", height=400, margin=dict(l=120,r=40,t=20,b=40))
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.warning(f"Tornado chart skipped: {e}")

    st.divider()
    st.subheader("Per-segment breakdown")
    seg_df = result.df_capex if not result.df_capex.empty else result.df_attributed
    display_cols = ["segment_id","typology","kwp_dc","p50_annual_kwh","segment_epc_usd","offtaker_type","self_consumption_pct"]
    cols_present = [c for c in display_cols if c in seg_df.columns]
    if cols_present:
        st.dataframe(seg_df[cols_present].round(2), use_container_width=True, height=350)
    else:
        st.dataframe(seg_df.round(2), use_container_width=True, height=350)

    st.divider()
    out_buf = io.StringIO()
    seg_df.to_csv(out_buf, index=False)
    st.download_button("Download results (CSV)", data=out_buf.getvalue(), file_name=f"scoping_{estate.replace(' ','_')}.csv", mime="text/csv")

else:
    st.info("Upload a segment CSV or select a preset, then click **Run scoping**.")

# T108: Run history (always visible)
if persistence.is_available():
    st.divider()
    with st.expander("📜 Run history (most recent 20)", expanded=False):
        recent = persistence.list_recent_runs(limit=20)
        if not recent:
            st.caption("No runs saved yet.")
        else:
            history_rows = []
            for r in recent:
                snap = r.get("results_snapshot") or {}
                history_rows.append({
                    "Run": (r["id"] or "")[:8],
                    "Label": r.get("run_label") or "—",
                    "Estate": r.get("estate"),
                    "Envelope MWp": snap.get("envelope_mwp"),
                    "EPC $M": snap.get("epc_usd_m"),
                    "Equity IRR": snap.get("equity_irr"),
                    "Y10 exit IRR": snap.get("y10_exit_irr"),
                    "DSCR min": snap.get("dscr_min"),
                    "By": r.get("ran_by_email"),
                    "At (UTC)": r.get("ran_at"),
                })
            history_df = pd.DataFrame(history_rows)
            st.dataframe(history_df, use_container_width=True, hide_index=True)

st.divider()
st.caption("Engine: NC-METH-001 v1.1.0 · Parameters: NC-PARAM-001 v1.1.1 · Internal - not for redistribution")
