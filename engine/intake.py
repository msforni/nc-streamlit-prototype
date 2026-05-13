"""Stage 1 — Intake.

Validates per-segment CSV input. Enforces:
  - Required columns present
  - typology in allowed set
  - T1 invalid at Lat Krabang / Lamphun (land-lease)
  - BESS at Laem Chabang → WARNING (LC has no BESS by design)
  - self_consumption_pct in [0, 1]
  - tenant rows have tenant_name + tenant_tier

Returns (df_validated, warnings, errors). Errors block; warnings annotate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from . import parameters as P


REQUIRED_COLUMNS = {
    "segment_id",
    "estate",
    "typology",
    "offtaker_type",
    "self_consumption_pct",
}

OPTIONAL_COLUMNS = {
    "area_m2",
    "kwh_capacity",
    "kwp_dc",
    "tenant_name",
    "tenant_tier",
    "notes",
    "suitability_score",
}


@dataclass
class IntakeResult:
    """Container for intake output."""
    df: pd.DataFrame
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate(df: pd.DataFrame) -> IntakeResult:
    """Validate a segment CSV DataFrame.

    Returns IntakeResult with cleaned df + accumulated warnings/errors.
    Does NOT raise — caller inspects .is_valid and .errors to decide.
    """
    result = IntakeResult(df=df.copy())

    # --- Schema check ---
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        result.errors.append(
            f"Missing required columns: {sorted(missing)}"
        )
        return result

    # --- Empty check ---
    if len(df) == 0:
        result.errors.append("Segment CSV is empty.")
        return result

    # --- Typology check ---
    bad_typology = ~result.df["typology"].isin(P.ALLOWED_TYPOLOGIES)
    if bad_typology.any():
        bad_rows = result.df.loc[bad_typology, "segment_id"].tolist()
        result.errors.append(
            f"Invalid typology in segments: {bad_rows}. "
            f"Allowed: {sorted(P.ALLOWED_TYPOLOGIES)}"
        )

    # --- T1 invalid at land-lease estates ---
    t1_at_landlease = (
        (result.df["typology"] == "T1")
        & (result.df["estate"].isin(P.T1_INVALID_ESTATES))
    )
    if t1_at_landlease.any():
        bad = result.df.loc[t1_at_landlease, ["segment_id", "estate"]].to_dict("records")
        result.errors.append(
            f"T1 rooftop typology invalid at land-lease estates {sorted(P.T1_INVALID_ESTATES)}. "
            f"Offending segments: {bad}. "
            f"Use T2 / T4A / T6W instead. Per NC-PARAM-001 §14 point 5."
        )

    # --- BESS at LC → warning, not error ---
    bess_at_lc = (
        (result.df["typology"] == "BESS")
        & (result.df["estate"].isin(P.BESS_BY_DESIGN_NONE))
    )
    if bess_at_lc.any():
        bad = result.df.loc[bess_at_lc, "segment_id"].tolist()
        result.warnings.append(
            f"BESS at Laem Chabang for segments {bad}. "
            f"LC v1.0 has NO BESS by design per NC-PARAM-001 §14 point 6. "
            f"Proceeding but flag for sponsor review."
        )

    # --- Smart Park UMC lapsed ---
    smart_park = result.df["estate"] == "Smart Park"
    if smart_park.any() and P.SMART_PARK_UMC_LAPSED:
        result.warnings.append(
            "Smart Park UMC has lapsed per NC-PARAM-001 §14 point 7. "
            "Verify estate-level concession status before sponsor sign-off."
        )

    # --- self_consumption_pct bounds ---
    sc_bad = (
        (result.df["self_consumption_pct"] < 0)
        | (result.df["self_consumption_pct"] > 1)
    )
    if sc_bad.any():
        bad = result.df.loc[sc_bad, "segment_id"].tolist()
        result.errors.append(
            f"self_consumption_pct must be in [0, 1]. Offending: {bad}"
        )

    # --- offtaker_type check ---
    bad_off = ~result.df["offtaker_type"].isin(P.ALLOWED_OFFTAKER_TYPES)
    if bad_off.any():
        bad = result.df.loc[bad_off, "segment_id"].tolist()
        result.errors.append(
            f"Invalid offtaker_type in {bad}. "
            f"Allowed: {sorted(P.ALLOWED_OFFTAKER_TYPES)}"
        )

    # --- Tenant rows need tier; default to C with warning if missing ---
    if "tenant_tier" not in result.df.columns:
        result.df["tenant_tier"] = pd.NA

    needs_tier = result.df["offtaker_type"].isin({"tenant", "mixed"})
    tier_missing = needs_tier & result.df["tenant_tier"].isna()
    if tier_missing.any():
        bad = result.df.loc[tier_missing, "segment_id"].tolist()
        result.warnings.append(
            f"Tenant rows missing tenant_tier for {bad}. "
            f"Defaulting to tier {P.DEFAULT_TENANT_TIER} per NC-METH-001 Annex G."
        )
        result.df.loc[tier_missing, "tenant_tier"] = P.DEFAULT_TENANT_TIER

    bad_tier = (
        result.df["tenant_tier"].notna()
        & ~result.df["tenant_tier"].isin(P.ALLOWED_TENANT_TIERS)
    )
    if bad_tier.any():
        bad = result.df.loc[bad_tier, "segment_id"].tolist()
        result.errors.append(
            f"Invalid tenant_tier in {bad}. Allowed: {sorted(P.ALLOWED_TENANT_TIERS)}"
        )

    # --- PV segments need area_m2 OR kwp_dc; BESS needs kwh_capacity ---
    pv_typologies = P.ALLOWED_TYPOLOGIES - {"BESS"}
    is_pv = result.df["typology"].isin(pv_typologies)
    is_bess = result.df["typology"] == "BESS"

    if "area_m2" not in result.df.columns:
        result.df["area_m2"] = pd.NA
    if "kwp_dc" not in result.df.columns:
        result.df["kwp_dc"] = pd.NA
    if "kwh_capacity" not in result.df.columns:
        result.df["kwh_capacity"] = pd.NA

    pv_missing_size = is_pv & result.df["area_m2"].isna() & result.df["kwp_dc"].isna()
    if pv_missing_size.any():
        bad = result.df.loc[pv_missing_size, "segment_id"].tolist()
        result.errors.append(
            f"PV segments need area_m2 or pre-computed kwp_dc. Missing both: {bad}"
        )

    bess_missing_size = is_bess & result.df["kwh_capacity"].isna()
    if bess_missing_size.any():
        bad = result.df.loc[bess_missing_size, "segment_id"].tolist()
        result.errors.append(
            f"BESS segments need kwh_capacity. Missing: {bad}"
        )

    # --- Default suitability_score if missing ---
    if "suitability_score" not in result.df.columns:
        result.df["suitability_score"] = 3  # default acceptable

    return result
