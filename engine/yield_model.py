"""Stage 3 — Yield model.

Per-segment P50 / P90 yield. Mapping driven by estate → climate zone in
NC-PARAM-001 §5. Degradation modeled at 1.0%/yr (TOPCon canonical) over the
25-year operating life.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import parameters as P


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Add `p50_yield_kwh_kwp_yr`, `p90_yield_kwh_kwp_yr`,
    `p50_annual_kwh`, `p90_annual_kwh` to the DataFrame.

    P50 looked up from estate; P90 = P50 × 0.90 (canonical).
    Degradation applied downstream in financial.py via year-by-year multiplier.
    """
    out = df.copy()

    # Map estate to P50 yield (kWh/kWp/yr)
    out["p50_yield_kwh_kwp_yr"] = (
        out["estate"]
        .map(P.ESTATE_YIELD_ZONE)
        .fillna(P.YIELD_BANGKOK_P50)  # fallback for unmapped estates
    )
    out["p90_yield_kwh_kwp_yr"] = out["p50_yield_kwh_kwp_yr"] * P.YIELD_P90_FACTOR

    # Year-1 generation (kWh) — before degradation
    out["p50_annual_kwh"] = out["kwp_dc"] * out["p50_yield_kwh_kwp_yr"]
    out["p90_annual_kwh"] = out["kwp_dc"] * out["p90_yield_kwh_kwp_yr"]

    return out


def degradation_factor(year: int, degradation_rate: float = P.ESA_DEGRADATION) -> float:
    """Return the cumulative degradation factor at end of `year`.

    year=1 → (1 - r)^0 = 1.0 (year 1 is the full nameplate year)
    year=2 → (1 - r)^1
    year=25 → (1 - r)^24
    """
    if year < 1:
        return 1.0
    return (1.0 - degradation_rate) ** (year - 1)


def generation_curve(kwp: float, p50: float, years: int = P.ASSET_USEFUL_LIFE) -> np.ndarray:
    """Annual generation array (years × 1) with degradation applied.

    Returns kWh per year for years 1..years.
    """
    return np.array([
        kwp * p50 * degradation_factor(y)
        for y in range(1, years + 1)
    ])
