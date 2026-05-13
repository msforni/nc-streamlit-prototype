"""
NewCo Investment Scoping Calculator — Streamlit UI
NC-STREAMLIT-001 v0.1

Run with: streamlit run app.py
"""

import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import parameters as P
from engine.pipeline import run


# ─────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NewCo Scoping Calculator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("NewCo Investment Scoping Calculator")
st.caption(
    "v0.1 prototype · NC-METH-001 canonical pipeline · IEAT-Industrial only"
)

# ─────────────────────────────────────────────────────────────────────
# Sidebar — configuration
# ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuration")

    estate = st.selectbox(
        "Estate",
        options=[
            "Laem Chabang",
            "Bangpoo",
            "Bangplee",
            "Map Ta Phut",
            "Map Ta Phut Port",
            "Lat Krabang",
            "Lamphun",
            "Other",
        ],
        index=0,
        help="LC is the canonical validation estate. Bangplee/MTP are the v0.1 target new estates.",
    )

    st.divider()
    st.subheader("Debt structure")

    ltv = st.slider(
        "Debt LTV (%)",
        min_value=30,
        max_value=75,
        value=60,
        step=1,
        help="LC sponsor base = 60%. Lender-sized = 52%. 70%+ breaches DSCR at LC.",
    )
    rate = st.number_input(
        "Interest rate (%)",
        min_value=4.0,
        max_value=10.0,
        value=6.0,
        step=0.25,
        help="LC = 6.0% blended; EXIM standard 5.75%/12yr.",
    )
    tenor = st.number_input(
        "Tenor (years)",
        min_value=5,
        max_value=20,
        value=12,
        step=1,
    )

    st.divider()
    st.subheader("Tariff override")

    tariff_default = P.TARIFF_BY_ESTATE.get(estate, 3.85)
    tariff = st.number_input(
        "PPA tariff (THB/kWh)",
        min_value=2.50,
        max_value=5.50,
        value=float(tariff_default),
        step=0.05,
        help=f"Default for {estate}: {tariff_default} THB/kWh",
    )
    tariff_escalation = st.number_input(
        "Tariff escalation (%/yr)",
        min_value=0.0,
        max_value=4.0,
        value=0.0 if estate == "Laem Chabang" else 1.5,
        step=0.1,
    )

    st.divider()
    st.subheader("BOI tax holiday")

    boi_years = st.selectbox(
        "Tax holiday tenor",
        options=[8, 13],
        index=0,
        help="8 = standard Activity 5.2.1. 13 = EEC enhancement (under evaluation, not yet awarded).",
    )

    st.divider()
    st.caption(
        "Parameters locked from NC-PARAM-001 v1.1.1: "
        f"FX {P.FX_THB_USD}, grid EF {P.GRID_EF_TCO2_PER_MWH}, "
        f"BESS ${P.BESS_USD_PER_KWH}/kWh"
    )

# ─────────────────────────────────────────────────────────────────────
# Main pane — input
# ─────────────────────────────────────────────────────────────────────

col_upload, col_preset = st.columns([2, 1])

with col_upload:
    st.subheader("1. Upload segment CSV")
    uploaded = st.file_uploader(
        "CSV with per-segment data (see schemas/segment_csv_schema.json)",
        type=["csv"],
        help="Required columns: segment_id, estate, typology, area_m2 (or kwh_capacity for BESS), offtaker_type, self_consumption_pct",
    )

with col_preset:
    st.subheader("Or load a preset")
    preset_choice = st.radio(
        "Preset",
        ["None", "LC v1.0 canonical", "Bangplee template", "MTP template"],
        label_visibility="collapsed",
    )

# Determine the dataframe source
df_input = None
data_source = None

if uploaded is not None:
    df_input = pd.read_csv(uploaded)
    data_source = f"Uploaded: {uploaded.name}"
elif preset_choice != "None":
    preset_files = {
        "LC v1.0 canonical": "data/lc_v1_segments.csv",
        "Bangplee template": "data/bangplee_template.csv",
        "MTP template": "data/mtp_template.csv",
    }
    preset_path = Path(preset_files[preset_choice])
    if preset_path.exists():
        df_input = pd.read_csv(preset_path)
        data_source = f"Preset: {preset_choice}"
    else:
        st.warning(f"Preset file not found at {preset_path}")

if df_input is not None:
    st.success(f"Loaded: {data_source} — {len(df_input)} segments")
    with st.expander("Preview input data", expanded=False):
        st.dataframe(df_input.head(20), use_container_width=True)

# ─────────────────────────────────────────────────────────────────────
# Run scoping
# ─────────────────────────────────────────────────────────────────────

st.divider()

run_button = st.button(
    "Run scoping",
    type="primary",
    disabled=(df_input is None),
    use_container_width=True,
)

if run_button and df_input is not None:
    with st.spinner("Running pipeline (Stages 1-7)…"):
        try:
            result = run(
                df_input,
                ltv=ltv / 100,
                interest_rate=rate / 100,
                tenor_years=tenor,
                tariff_thb_per_kwh=tariff,
                tariff_escalation_pct=tariff_escalation / 100,
                boi_years=boi_years,
                estate=estate,
            )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # ─────────────────────────────────────────────────────────────────
    # Headline metrics
    # ─────────────────────────────────────────────────────────────────
    st.subheader("Headline metrics")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Total envelope",
        f"{result['total_mwp']:.2f} MWp",
        f"{result['n_segments']} segments",
    )
    m2.metric("EPC", f"${result['epc_usd_m']:.2f}M")
    m3.metric(
        "Total project cost",
        f"${result['tpc_usd_m']:.2f}M",
        f"+{(result['tpc_usd_m']/result['epc_usd_m']-1)*100:.0f}% soft costs",
    )
    m4.metric(
        "P50 generation",
        f"{result['p50_mwh_yr']:,.0f} MWh/yr",
    )

    m5, m6, m7, m8 = st.columns(4)
    m5.metric(
        f"Sponsor IRR @ {ltv}% LTV",
        f"{result['sponsor_irr']*100:.1f}%",
    )
    m6.metric(
        "DSCR (P90 lender-sized)",
        f"{result['dscr_p90']:.2f}×",
        delta=(
            "BREACH" if result['dscr_p90'] < 1.10
            else "Marginal" if result['dscr_p90'] < 1.30
            else "OK"
        ),
        delta_color=(
            "inverse" if result['dscr_p90'] < 1.30 else "normal"
        ),
    )
    m7.metric(
        "Payback (blended)",
        f"{result['payback_years']:.1f} yrs",
    )
    m8.metric(
        "Y10 exit IRR @ 13.5×",
        f"{result['y10_exit_irr']*100:.1f}%",
        f"MOIC {result['y10_moic']:.2f}×",
    )

    # ─────────────────────────────────────────────────────────────────
    # LC validation
    # ─────────────────────────────────────────────────────────────────
    if estate == "Laem Chabang":
        st.divider()
        st.subheader("LC v1.0 ground-truth validation")
        check = lc_ground_truth_check(result)
        if check["pass"]:
            st.success(
                f"✅ Engine within ±0.5% of NC-FM-LC-001 v1.0 canonical "
                f"(max deviation: {check['max_deviation_pct']:.2f}%)"
            )
        else:
            st.warning(
                f"⚠ Engine drift detected. Max deviation: "
                f"{check['max_deviation_pct']:.2f}% — investigate before relying on outputs."
            )
        with st.expander("Validation detail", expanded=False):
            st.dataframe(pd.DataFrame(check["comparisons"]), use_container_width=True)

    # ─────────────────────────────────────────────────────────────────
    # Per-segment table
    # ─────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Per-segment breakdown")

    seg_df = result["segments"]
    display_cols = [
        "segment_id", "typology", "kwp_dc", "p50_kwh_yr",
        "unit_cost_per_kwp", "segment_capex_usd", "offtaker_type",
        "tenant_name", "self_consumption_pct", "year1_revenue_usd",
    ]
    cols_present = [c for c in display_cols if c in seg_df.columns]
    st.dataframe(
        seg_df[cols_present].round(2),
        use_container_width=True,
        height=350,
    )

    # ─────────────────────────────────────────────────────────────────
    # Cashflow chart
    # ─────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Annual cashflow (25 years)")

    cf = result["cashflow"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cf["year"], y=cf["revenue_usd_m"],
        mode="lines", name="Revenue",
        line=dict(color="#1f77b4", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=cf["year"], y=cf["opex_usd_m"],
        mode="lines", name="OPEX",
        line=dict(color="#64748B", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=cf["year"], y=cf["debt_service_usd_m"],
        mode="lines", name="Debt service",
        line=dict(color="#F59E0B", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=cf["year"], y=cf["fcfe_usd_m"],
        mode="lines", name="Free cash flow to equity",
        line=dict(color="#0D9488", width=3),
        fill="tozeroy",
        fillcolor="rgba(13, 148, 136, 0.1)",
    ))
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="USD millions",
        hovermode="x unified",
        height=400,
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────
    # Sensitivity tornado
    # ─────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Sensitivity tornado (IRR ± bps from base)")

    sens = result["sensitivity"]
    sens_df = pd.DataFrame(sens).sort_values("magnitude_bps", ascending=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        y=sens_df["dimension"],
        x=sens_df["upside_bps"],
        name="Upside",
        orientation="h",
        marker_color="#0D9488",
    ))
    fig2.add_trace(go.Bar(
        y=sens_df["dimension"],
        x=sens_df["downside_bps"],
        name="Downside",
        orientation="h",
        marker_color="#F59E0B",
    ))
    fig2.update_layout(
        barmode="overlay",
        xaxis_title="IRR delta (bps)",
        height=400,
        margin=dict(l=120, r=40, t=20, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────
    # Download outputs
    # ─────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Export")

    out_buf = io.StringIO()
    seg_df.to_csv(out_buf, index=False)
    st.download_button(
        "Download per-segment results (CSV)",
        data=out_buf.getvalue(),
        file_name=f"scoping_results_{estate.replace(' ', '_')}.csv",
        mime="text/csv",
    )

else:
    st.info(
        "Upload a segment CSV or select a preset, then click **Run scoping**."
    )

# Footer
st.divider()
st.caption(
    "Engine: NC-METH-001 v1.1.0 · Parameters: NC-PARAM-001 v1.1.1 · "
    "Validation: NC-FM-LC-001 v1.0 · Internal — not for redistribution"
)
