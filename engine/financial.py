"""Stage 6 — Financial model.

25-year cashflow → IRR (equity), DSCR (per year), NPV, MOIC, payback, Y10 exit.

Mechanics:
  - Revenue = annual_kwh × tariff × credit_factor (degraded yearly)
  - Tariff escalates per ESCALATION_* parameter for the program
  - OPEX escalates 2.5%/yr
  - Debt service: equal-amortization (mortgage-style) over tenor, 1yr grace
  - BOI tax holiday for first 8 years (or 13 for EEC enhancement)
  - Carbon revenue: solar T-VER × delivery confidence (v0.1 hard-coded)
  - Terminal value at year 10 = 13.5× EBITDA (NewCo exit case)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import numpy_financial as npf
import pandas as pd

from . import parameters as P


@dataclass
class FinancialInputs:
    """Inputs to the financial model. Defaults to LC v1.0 canonical."""
    tariff_thb_kwh: float = P.TARIFF_IEAT_LC
    tariff_escalation: float = P.ESCALATION_IEAT_LC  # 0% for LC
    fx_thb_usd: float = P.FX_THB_USD_MAIN
    debt_ltv: float = P.LTV_SPONSOR_BASE
    debt_rate: float = P.DEBT_RATE_IEAT_LC
    debt_tenor_years: int = P.DEBT_TENOR_YEARS
    debt_grace_years: int = P.DEBT_GRACE_YEARS
    boi_years: int = P.BOI_STANDARD_TENOR
    cit_rate: float = P.CIT_RATE_THAILAND
    asset_life_years: int = P.ASSET_USEFUL_LIFE
    degradation_rate: float = P.ESA_DEGRADATION
    opex_escalation: float = P.OPEX_ESCALATION
    discount_rate: float = P.ESA_DISCOUNT_RATE
    exit_multiple: float = P.EXIT_MULTIPLE_LC_Y10
    exit_year: int = P.EXIT_YEAR
    include_carbon_revenue: bool = False  # LC = False by design
    carbon_price_usd: float = P.CARBON_SOLAR_TVER_USD
    carbon_delivery_factor: float = P.CARBON_DELIVERY_DEFAULT
    tenant_consent_pct: float = 1.0  # for sensitivity
    # NC-SPRINT-002 LC drift fix: explicit LTV basis. Default EPC per
    # NC-FM-LC-001 v1.0 and standard PF practice. Pipeline resolves the
    # per-estate value from P.LTV_BASIS_BY_ESTATE when this is left as None.
    ltv_basis: Optional[str] = None
    # NC-SPRINT-002 Option X: revenue basis. BTM_FULL = full p50 generation
    # at BTM tariff (canonical LC assumption). ATTRIBUTED = haircut by SC%
    # and credit_factor (v0.1 conservative default — wrong for canonical LC).
    # Pipeline resolves per-estate value from P.REVENUE_BASIS_BY_ESTATE when
    # this is left as None.
    revenue_basis: Optional[str] = None


@dataclass
class FinancialResults:
    """Outputs of the financial model."""
    envelope_mwp: float
    epc_usd_m: float
    total_project_cost_usd_m: float
    debt_usd_m: float
    equity_usd_m: float
    year1_revenue_usd_m: float
    year1_opex_usd_m: float
    year1_ebitda_usd_m: float
    equity_irr: float
    project_irr: float
    npv_at_discount_usd_m: float
    moic_y10: float
    payback_years: float
    dscr_min: float
    dscr_avg: float
    dscr_breach: bool
    y10_exit_irr: float
    cashflow_df: pd.DataFrame
    dscr_series: pd.Series = field(default_factory=pd.Series)
    dscr_min_p90: float = 0.0


def model(
    df_attributed: pd.DataFrame,
    epc_usd: float,
    total_project_cost_usd: float,
    opex_year1_usd: float,
    inputs: Optional[FinancialInputs] = None,
) -> FinancialResults:
    """Run the 25-year financial model.

    `df_attributed` must come from offtaker.attribute() and have:
      - p50_annual_kwh (year 1, pre-degradation)
      - attributed_consumption_kwh (year 1, post-credit, post-SC)
      - kwp_dc

    Returns FinancialResults with the cashflow DataFrame attached.
    """
    if inputs is None:
        inputs = FinancialInputs()

    # NC-SPRINT-002 Option X: pick the revenue source column based on basis.
    # BTM_FULL: revenue = full p50 generation × tariff (canonical LC).
    # ATTRIBUTED: revenue = gen × SC% × credit (conservative v0.1 default).
    revenue_basis = (inputs.revenue_basis or P.REVENUE_BASIS_DEFAULT).upper()
    if revenue_basis == P.REVENUE_BASIS_BTM_FULL and "btm_full_consumption_kwh" in df_attributed.columns:
        consumption_col = "btm_full_consumption_kwh"
    else:
        consumption_col = "attributed_consumption_kwh"

    attr_y1_kwh = float(df_attributed[consumption_col].sum())

    # Build year-by-year cashflow
    years = list(range(0, inputs.asset_life_years + 1))  # Y0..Y25
    n_years = inputs.asset_life_years

    # Generation per year (with degradation)
    degradation = np.array([
        (1.0 - inputs.degradation_rate) ** (y - 1) if y >= 1 else 0.0
        for y in years
    ])
    annual_kwh = attr_y1_kwh * degradation  # array[26]

    # Revenue per year (energy)
    tariff_escalation_factor = np.array([
        (1.0 + inputs.tariff_escalation) ** max(y - 1, 0)
        for y in years
    ])
    annual_revenue_thb = annual_kwh * inputs.tariff_thb_kwh * tariff_escalation_factor
    annual_revenue_usd = annual_revenue_thb / inputs.fx_thb_usd

    # Optional carbon revenue
    annual_carbon_revenue_usd = np.zeros(len(years))
    if inputs.include_carbon_revenue:
        # carbon revenue = generation × grid_EF × carbon_price × delivery_factor
        # Note: T-VER price not escalated in v0.1
        annual_carbon_revenue_usd = (
            annual_kwh / 1000.0  # kWh → MWh
            * P.GRID_EF_TCO2_PER_MWH
            * inputs.carbon_price_usd
            * inputs.carbon_delivery_factor
        )

    annual_total_revenue_usd = annual_revenue_usd + annual_carbon_revenue_usd

    # OPEX per year (escalating)
    opex_escalation_factor = np.array([
        (1.0 + inputs.opex_escalation) ** max(y - 1, 0)
        for y in years
    ])
    annual_opex_usd = opex_year1_usd * opex_escalation_factor
    # Y0 has no OPEX (construction year)
    annual_opex_usd[0] = 0.0
    # Also zero out Y0 revenue (construction year)
    annual_total_revenue_usd[0] = 0.0
    annual_revenue_usd[0] = 0.0
    annual_carbon_revenue_usd[0] = 0.0
    annual_kwh[0] = 0.0

    ebitda_usd = annual_total_revenue_usd - annual_opex_usd

    # Debt service
    # NC-SPRINT-002 LC drift resolution (May 2026): debt sized off EPC by
    # default, per NC-FM-LC-001 v1.0 canonical and standard PF practice for
    # hard-asset senior debt. Configurable via inputs.ltv_basis for asset
    # classes (e.g. some sponsor-IRR comparables gear off TPC).
    ltv_basis = (inputs.ltv_basis or P.LTV_BASIS_DEFAULT).upper()
    if ltv_basis == P.LTV_BASIS_TPC:
        debt_basis_usd = total_project_cost_usd
    else:
        # Default to EPC for any unrecognized value (fail safe to canonical).
        debt_basis_usd = epc_usd
    debt_usd = debt_basis_usd * inputs.debt_ltv
    equity_usd = total_project_cost_usd - debt_usd
    debt_service_usd = _debt_service_schedule(
        principal=debt_usd,
        rate=inputs.debt_rate,
        tenor=inputs.debt_tenor_years,
        grace=inputs.debt_grace_years,
        total_years=n_years,
    )

    # Tax: BOI exempts CIT for boi_years; afterwards 20% on EBITDA (simplified —
    # ignoring depreciation shield since solar PV gets accelerated dep that
    # roughly cancels out over 8-13 yr horizon for an A1+ BOI project).
    # v0.1: approximate tax as max(0, EBITDA - debt_interest) × cit_rate for
    # years > boi_years.
    interest_schedule = _interest_schedule(
        principal=debt_usd,
        rate=inputs.debt_rate,
        tenor=inputs.debt_tenor_years,
        grace=inputs.debt_grace_years,
        total_years=n_years,
    )

    tax_usd = np.zeros(len(years))
    for i, y in enumerate(years):
        if y == 0 or y <= inputs.boi_years:
            tax_usd[i] = 0.0
        else:
            taxable = max(0.0, ebitda_usd[i] - interest_schedule[i])
            tax_usd[i] = taxable * inputs.cit_rate

    # Free cash flow to equity
    fcfe_usd = ebitda_usd - debt_service_usd - tax_usd
    # Y0: equity outflow
    fcfe_usd[0] = -equity_usd

    # DSCR (per year, debt-service years only)
    cfads_usd = ebitda_usd - tax_usd  # cashflow available for debt service
    with np.errstate(divide="ignore", invalid="ignore"):
        dscr = np.where(
            debt_service_usd > 0,
            cfads_usd / debt_service_usd,
            np.nan,
        )

    # Equity IRR over 25 years
    equity_irr = _safe_irr(fcfe_usd.tolist())

    # Project IRR (unlevered)
    project_cf = ebitda_usd.copy()
    project_cf[0] = -total_project_cost_usd
    project_irr = _safe_irr(project_cf.tolist())

    # NPV @ discount rate
    npv_usd = npf.npv(inputs.discount_rate, fcfe_usd)

    # Debt balance schedule (used by Y10 exit + reporting)
    debt_balance_usd = _debt_balance_schedule(
        principal=debt_usd,
        rate=inputs.debt_rate,
        tenor=inputs.debt_tenor_years,
        grace=inputs.debt_grace_years,
        total_years=n_years,
    )

    # Y10 exit: equity value = EV − closing debt − transaction costs.
    # NC-SPRINT-002 Option X fix (May 2026): previously the engine added the
    # full enterprise value to FCFE_Y10, which overstated terminal proceeds
    # by the Y10 closing debt balance and ignored exit costs. Canonical
    # NC-FM-LC-001 v1.0 Y10_Exit tab: Net distributable = EV − closing debt
    # − 3% transaction costs (then split per JV waterfall, out of engine scope).
    y10_index = inputs.exit_year
    y10_ebitda = ebitda_usd[y10_index]
    enterprise_value = y10_ebitda * inputs.exit_multiple
    y10_closing_debt = float(debt_balance_usd[y10_index])
    gross_equity_value = enterprise_value - y10_closing_debt
    terminal_to_equity = gross_equity_value * (1.0 - P.EXIT_COSTS_PCT)
    # Add net equity terminal to FCFE at year 10, truncate cashflow there
    fcfe_for_exit = fcfe_usd[:y10_index + 1].copy()
    fcfe_for_exit[-1] += terminal_to_equity
    y10_irr = _safe_irr(fcfe_for_exit.tolist())

    # MOIC at Y10 = (sum of FCFE Y1..Y10 + net equity terminal) / equity outflow
    total_inflows_y10 = fcfe_usd[1:y10_index + 1].sum() + terminal_to_equity
    moic_y10 = total_inflows_y10 / equity_usd if equity_usd > 0 else float("nan")

    # Payback (years to recover equity, using cumulative FCFE excluding Y0)
    cum_fcfe = np.cumsum(fcfe_usd[1:])
    payback = _payback_year(cum_fcfe, equity_usd)

    # DSCR diagnostics
    dscr_valid = dscr[~np.isnan(dscr)]
    dscr_min = float(np.min(dscr_valid)) if len(dscr_valid) > 0 else float("nan")
    dscr_avg = float(np.mean(dscr_valid)) if len(dscr_valid) > 0 else float("nan")
    dscr_breach = bool(dscr_min < P.DSCR_COVENANT_MIN) if not np.isnan(dscr_min) else False

    # P90 DSCR: revenue × (P90 yield / P50 yield) = 0.9, opex and DS unchanged.
    # Used in canonical LC IC headline ("Min DSCR P90 1.13x").
    cfads_p90_usd = (annual_total_revenue_usd * P.YIELD_P90_FACTOR) - annual_opex_usd - tax_usd
    with np.errstate(divide="ignore", invalid="ignore"):
        dscr_p90 = np.where(
            debt_service_usd > 0,
            cfads_p90_usd / debt_service_usd,
            np.nan,
        )
    dscr_p90_valid = dscr_p90[~np.isnan(dscr_p90)]
    dscr_min_p90 = float(np.min(dscr_p90_valid)) if len(dscr_p90_valid) > 0 else float("nan")

    # Build cashflow dataframe
    cashflow_df = pd.DataFrame({
        "year": years,
        "generation_kwh": annual_kwh,
        "energy_revenue_usd": annual_revenue_usd,
        "carbon_revenue_usd": annual_carbon_revenue_usd,
        "total_revenue_usd": annual_total_revenue_usd,
        "opex_usd": annual_opex_usd,
        "ebitda_usd": ebitda_usd,
        "interest_usd": interest_schedule,
        "debt_service_usd": debt_service_usd,
        "tax_usd": tax_usd,
        "fcfe_usd": fcfe_usd,
        "dscr": dscr,
    })

    return FinancialResults(
        envelope_mwp=float(df_attributed["kwp_dc"].sum() / 1_000.0),
        epc_usd_m=epc_usd / 1_000_000.0,
        total_project_cost_usd_m=total_project_cost_usd / 1_000_000.0,
        debt_usd_m=debt_usd / 1_000_000.0,
        equity_usd_m=equity_usd / 1_000_000.0,
        year1_revenue_usd_m=annual_total_revenue_usd[1] / 1_000_000.0,
        year1_opex_usd_m=annual_opex_usd[1] / 1_000_000.0,
        year1_ebitda_usd_m=ebitda_usd[1] / 1_000_000.0,
        equity_irr=equity_irr,
        project_irr=project_irr,
        npv_at_discount_usd_m=npv_usd / 1_000_000.0,
        moic_y10=moic_y10,
        payback_years=payback,
        dscr_min=dscr_min,
        dscr_avg=dscr_avg,
        dscr_breach=dscr_breach,
        y10_exit_irr=y10_irr,
        cashflow_df=cashflow_df,
        dscr_series=pd.Series(dscr, index=years, name="dscr"),
        dscr_min_p90=dscr_min_p90,
    )


# ============================================================
# Helpers
# ============================================================

def _debt_service_schedule(
    principal: float,
    rate: float,
    tenor: int,
    grace: int,
    total_years: int,
) -> np.ndarray:
    """Equal-payment (mortgage-style) debt service schedule, with grace period.

    During grace: interest-only payment.
    After grace, before tenor end: full annuity payment.
    After tenor: no payment.
    Returns array of length (total_years + 1), index 0 = Y0 (no payment).
    """
    service = np.zeros(total_years + 1)
    # During grace (Y1..Y_grace): interest only
    for y in range(1, grace + 1):
        if y <= total_years:
            service[y] = principal * rate
    # After grace (Y_{grace+1} ... Y_tenor): full annuity
    amortization_years = tenor - grace
    if amortization_years > 0 and rate > 0:
        annuity = principal * (rate * (1 + rate) ** amortization_years) / ((1 + rate) ** amortization_years - 1)
        for y in range(grace + 1, tenor + 1):
            if y <= total_years:
                service[y] = annuity
    return service


def _interest_schedule(
    principal: float,
    rate: float,
    tenor: int,
    grace: int,
    total_years: int,
) -> np.ndarray:
    """Per-year interest expense (declining balance after grace)."""
    interest = np.zeros(total_years + 1)
    balance = principal
    # Grace years: pay interest only, balance unchanged
    for y in range(1, grace + 1):
        if y <= total_years:
            interest[y] = balance * rate
    # Amortization: balance declines as principal is repaid
    amortization_years = tenor - grace
    if amortization_years > 0 and rate > 0:
        annuity = principal * (rate * (1 + rate) ** amortization_years) / ((1 + rate) ** amortization_years - 1)
        for y in range(grace + 1, tenor + 1):
            if y <= total_years:
                interest_y = balance * rate
                principal_y = annuity - interest_y
                interest[y] = interest_y
                balance = max(0.0, balance - principal_y)
    return interest


def _debt_balance_schedule(
    principal: float,
    rate: float,
    tenor: int,
    grace: int,
    total_years: int,
) -> np.ndarray:
    """End-of-year debt principal balance.

    Returns array of length (total_years + 1) where index k is the balance
    AT END of year k (after that year's amortization payment). Used for the
    Y10 exit calculation: terminal equity value = EV − closing debt balance.
    """
    balance_arr = np.zeros(total_years + 1)
    balance = principal
    balance_arr[0] = principal  # End of Y0 = full principal drawn
    # Grace years: balance unchanged
    for y in range(1, grace + 1):
        if y <= total_years:
            balance_arr[y] = balance
    # Amortization
    amortization_years = tenor - grace
    if amortization_years > 0 and rate > 0:
        annuity = principal * (rate * (1 + rate) ** amortization_years) / ((1 + rate) ** amortization_years - 1)
        for y in range(grace + 1, tenor + 1):
            if y <= total_years:
                interest_y = balance * rate
                principal_y = annuity - interest_y
                balance = max(0.0, balance - principal_y)
                balance_arr[y] = balance
    # After tenor: balance stays at 0
    return balance_arr


def _safe_irr(cashflows: list[float]) -> float:
    """numpy_financial.irr that returns NaN on failure instead of raising."""
    try:
        result = npf.irr(cashflows)
        if result is None or np.isnan(result):
            return float("nan")
        return float(result)
    except (ValueError, RuntimeError):
        return float("nan")


def _payback_year(cum_fcfe: np.ndarray, equity_outflow: float) -> float:
    """Linear-interpolated year at which cumulative FCFE crosses equity outflow."""
    target = equity_outflow
    for i, val in enumerate(cum_fcfe, start=1):
        if val >= target:
            if i == 1:
                return 1.0
            prev = cum_fcfe[i - 2]
            # Interpolate
            frac = (target - prev) / (val - prev) if val > prev else 0.0
            return float(i - 1 + frac)
    return float("nan")  # never paid back within asset life
