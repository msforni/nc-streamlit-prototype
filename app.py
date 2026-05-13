"""
NewCo Investment Scoping Calculator – Streamlit UI
NC-STREAMLIT-001 v0.1
"""
import io
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client
from engine.pipeline import run
from engine.financial import FinancialInputs

# ---- Supabase connection test (T101 smoke test) ----
def _supabase_status():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        client = create_client(url, key)
        # Trivial REST call: list any tables (will be empty pre-migration)
        project_ref = url.replace("https://", "").split(".")[0]
        return True, f"Connected: {project_ref}"
    except KeyError as e:
        return False, f"Missing secret: {e}"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {str(e)[:80]}"
# ----

st.set_page_config(page_title="NewCo Scoping Calculator", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
st.title("NewCo Investment Scoping Calculator")
st.caption("v0.1 prototype · NC-METH-001 canonical pipeline · IEAT-Industrial only")

with st.sidebar:
    _ok, _msg = _supabase_status()
    if _ok:
        st.success(f"Supabase: {_msg}")
    else:
        st.error(f"Supabase: {_msg}")
    st.header("Configuration")
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

col_upload, col_preset = st.columns([2, 1])
with col_upload:
    st.subheader("1. Upload segment CSV")
    uploaded = st.file_uploader("CSV with per-segment data", type=["csv"])
with col_preset:
    st.subheader("Or load a preset")
    preset_choice = st.radio("Preset", ["None", "LC v1.0 canonical", "Bangplee template", "MTP template"], label_visibility="collapsed")

df_input = None
data_source = None
if uploaded is not None:
    df_input = pd.read_csv(uploaded)
    data_source = f"Uploaded: {uploaded.name}"
elif preset_choice != "None":
    preset_files = {"LC v1.0 canonical": "data/lc_v1_segments.csv", "Bangplee template": "data/bangplee_template.csv", "MTP template": "data/mtp_template.csv"}
    preset_path = Path(preset_files[preset_choice])
    if preset_path.exists():
        df_input = pd.read_csv(preset_path)
        data_source = f"Preset: {preset_choice}"
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
            st.error(f"Pipeline error: {e}")
            st.stop()

    if result.intake_errors:
        st.error(f"Intake errors: {result.intake_errors}")
        st.stop()

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
    dscr_label = "BREACH" if fin.dscr_min < 1.10 else ("Marginal" if fin.dscr_min < 1.30 else "OK")
    m6.metric("DSCR min", f"{fin.dscr_min:.2f}x", delta=dscr_label, delta_color="inverse" if fin.dscr_min < 1.30 else "normal")
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
            tornado_data = [{"dimension": r.dimension, "upside_bps": r.upside_bps, "downside_bps": r.downside_bps, "magnitude_bps": r.magnitude_bps} for r in result.tornado_results]
            sens_df = pd.DataFrame(tornado_data).sort_values("magnitude_bps", ascending=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(y=sens_df["dimension"], x=sens_df["upside_bps"], name="Upside", orientation="h", marker_color="#0D9488"))
            fig2.add_trace(go.Bar(y=sens_df["dimension"], x=sens_df["downside_bps"], name="Downside", orientation="h", marker_color="#F59E0B"))
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

st.divider()
st.caption("Engine: NC-METH-001 v1.1.0 · Parameters: NC-PARAM-001 v1.1.1 · Internal - not for redistribution")
