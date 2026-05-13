"""Stage 2 — Sizing.

Per-segment kWp DC from typology coefficients. If `kwp_dc` is already set in
the input CSV, use it; otherwise derive from `area_m2` × typology coefficient.

For BESS, the size is kWh and we copy `kwh_capacity` to a `kwh_dc` column for
downstream uniformity.
"""

from __future__ import annotations

import pandas as pd

from . import parameters as P


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Add `kwp_dc` (for PV) and `kwh_dc` (for BESS) to the DataFrame.

    Input must have columns: typology, area_m2 (PV), kwh_capacity (BESS),
    optionally kwp_dc (overrides derivation).
    """
    out = df.copy()

    # PV: derive kWp from m² if not pre-computed
    pv_typologies = P.ALLOWED_TYPOLOGIES - {"BESS"}
    is_pv = out["typology"].isin(pv_typologies)

    if "kwp_dc" not in out.columns:
        out["kwp_dc"] = pd.NA

    # Where kwp_dc is missing and typology is PV, derive from area_m2
    needs_derivation = is_pv & out["kwp_dc"].isna()
    coef = out.loc[needs_derivation, "typology"].map(P.KWP_PER_M2_BY_TYPOLOGY)
    out.loc[needs_derivation, "kwp_dc"] = (
        out.loc[needs_derivation, "area_m2"].astype(float) * coef.astype(float)
    )

    # BESS: copy kwh_capacity → kwh_dc
    is_bess = out["typology"] == "BESS"
    if "kwh_dc" not in out.columns:
        out["kwh_dc"] = pd.NA
    out.loc[is_bess, "kwh_dc"] = out.loc[is_bess, "kwh_capacity"]

    # kwp_dc for BESS rows is 0 (BESS doesn't have a PV nameplate)
    out.loc[is_bess, "kwp_dc"] = 0.0

    # Ensure numeric dtypes
    out["kwp_dc"] = pd.to_numeric(out["kwp_dc"], errors="coerce").fillna(0.0)
    out["kwh_dc"] = pd.to_numeric(out["kwh_dc"], errors="coerce").fillna(0.0)

    return out


def envelope_mwp(df_sized: pd.DataFrame) -> float:
    """Total PV envelope in MWp DC."""
    return float(df_sized["kwp_dc"].sum() / 1_000.0)


def bess_capacity_mwh(df_sized: pd.DataFrame) -> float:
    """Total BESS capacity in MWh."""
    return float(df_sized["kwh_dc"].sum() / 1_000.0)
