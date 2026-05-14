"""Stage 5 — Offtaker attribution + per-tenant credit.

Allocates each segment's energy delivery between IEAT-direct and
tenant-attributed revenue streams. Tenant-attributed revenue is risk-adjusted
by tenant tier credit factor (per NC-METH-001 Annex G).
"""

from __future__ import annotations

import pandas as pd

from . import parameters as P


def attribute(df: pd.DataFrame) -> pd.DataFrame:
    """Add `credit_factor`, `attributed_consumption_kwh` to the DataFrame.

    Mechanics:
    - For `iea_direct`: credit_factor = 1.0 (IEAT itself is the offtaker)
    - For `tenant`: credit_factor = TENANT_TIER_CREDIT_FACTOR[tier]
    - For `mixed`: credit_factor = 0.5 × 1.0 + 0.5 × tier_factor (50/50 split)

    The credit factor is applied to revenue downstream in financial.py.
    """
    out = df.copy()

    def _row_credit(row) -> float:
        off = row["offtaker_type"]
        if off == "iea_direct":
            return 1.0
        if off == "tenant":
            tier = row.get("tenant_tier") or P.DEFAULT_TENANT_TIER
            return P.TENANT_TIER_CREDIT_FACTOR.get(tier, P.TENANT_TIER_CREDIT_FACTOR[P.DEFAULT_TENANT_TIER])
        if off == "mixed":
            tier = row.get("tenant_tier") or P.DEFAULT_TENANT_TIER
            tier_factor = P.TENANT_TIER_CREDIT_FACTOR.get(tier, P.TENANT_TIER_CREDIT_FACTOR[P.DEFAULT_TENANT_TIER])
            return 0.5 * 1.0 + 0.5 * tier_factor
        return 1.0  # fallback

    out["credit_factor"] = out.apply(_row_credit, axis=1)

    # ATTRIBUTED basis: generation × self_consumption_pct × credit_factor.
    # Conservative — non-self-consumed kWh assumed exported at zero revenue.
    out["attributed_consumption_kwh"] = (
        out["p50_annual_kwh"] * out["self_consumption_pct"] * out["credit_factor"]
    )

    # BTM_FULL basis: full generation × tariff (canonical LC v1.0 assumption).
    # SC% and credit_factor are metadata not revenue haircuts in this mode.
    # See NC-PARAM-001 REVENUE_BASIS_BY_ESTATE map.
    out["btm_full_consumption_kwh"] = out["p50_annual_kwh"].astype(float)

    # Excess generation (above SC%) is grid-export at lower revenue (or zero)
    # For v0.1 we assume 0 grid revenue (BTM-only). Track for sensitivity.
    out["excess_generation_kwh"] = (
        out["p50_annual_kwh"] * (1.0 - out["self_consumption_pct"])
    )

    return out


def tenant_consent_factor(
    df: pd.DataFrame,
    consent_pct: float = 1.0,
) -> pd.DataFrame:
    """Apply a tenant-consent haircut.

    Sensitivity dimension: what if only 80% of tenants sign ESAs?
    consent_pct is applied to attributed revenue from tenant + mixed rows
    across BOTH revenue-basis columns so downstream financial.model picks
    up the haircut regardless of which basis is active.
    """
    out = df.copy()
    tenant_rows = out["offtaker_type"].isin({"tenant", "mixed"})
    out.loc[tenant_rows, "attributed_consumption_kwh"] *= consent_pct
    if "btm_full_consumption_kwh" in out.columns:
        out.loc[tenant_rows, "btm_full_consumption_kwh"] *= consent_pct
    return out
