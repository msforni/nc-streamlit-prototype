"""Stage 4 — CAPEX build.

Per-typology unit cost × kWp = segment EPC.
Soft costs + financing fees + contingency + IDC = total project cost.

Annex H of NC-METH-001 has the LC canonical CAPEX stack. For non-LC estates,
this module uses the same per-typology values (Annex H) by default. Analyst
overrides per-segment via input CSV (`unit_cost_override` column if present).
"""

from __future__ import annotations

import pandas as pd

from . import parameters as P


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Add `unit_cost_usd_per_kwp`, `segment_epc_usd`, `segment_total_cost_usd`.

    Total cost = EPC × TOTAL_CAPEX_MULTIPLIER (1.165 by default).
    """
    out = df.copy()

    # Unit cost lookup by typology
    out["unit_cost_usd_per_kwp"] = out["typology"].map(P.CAPEX_BY_TYPOLOGY).fillna(0.0)

    # Override if explicitly provided
    if "unit_cost_override" in out.columns:
        override_mask = out["unit_cost_override"].notna() & (out["unit_cost_override"] > 0)
        out.loc[override_mask, "unit_cost_usd_per_kwp"] = out.loc[override_mask, "unit_cost_override"]

    # Segment EPC for PV
    out["segment_epc_usd"] = out["kwp_dc"] * out["unit_cost_usd_per_kwp"]

    # BESS contribution: kWh × $/kWh
    is_bess = out["typology"] == "BESS"
    out.loc[is_bess, "segment_epc_usd"] = (
        out.loc[is_bess, "kwh_dc"] * P.BESS_USD_PER_KWH_FULL
    )

    # Total project cost = EPC × multiplier
    out["segment_total_cost_usd"] = out["segment_epc_usd"] * P.TOTAL_CAPEX_MULTIPLIER

    return out


def total_epc_usd_m(df_capex: pd.DataFrame) -> float:
    """Total EPC across all segments in $M."""
    return float(df_capex["segment_epc_usd"].sum() / 1_000_000.0)


def total_project_cost_usd_m(df_capex: pd.DataFrame) -> float:
    """Total project cost (EPC + soft costs + IDC) across all segments in $M."""
    return float(df_capex["segment_total_cost_usd"].sum() / 1_000_000.0)


def opex_annual_usd(envelope_mwp: float, fx_thb_usd: float = P.FX_THB_USD_MAIN) -> float:
    """Year-1 OPEX in USD.

    OPEX_TOTAL_THB_PER_MWP × envelope_MWp / FX.
    Escalates 2.5%/yr downstream in financial.py.
    """
    opex_thb = envelope_mwp * P.OPEX_TOTAL_THB_PER_MWP
    return opex_thb / fx_thb_usd
