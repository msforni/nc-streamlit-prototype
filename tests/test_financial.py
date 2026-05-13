"""Tests for engine.financial — IRR / DSCR / NPV / MOIC unit tests."""

import pandas as pd
import pytest

from engine import financial, parameters as P


def _sample_segments():
    """A simple 5-segment fixture for unit testing."""
    return pd.DataFrame({
        "segment_id": [f"S-{i:03d}" for i in range(5)],
        "estate": ["Laem Chabang"] * 5,
        "typology": ["T1", "T1", "T2", "T4A", "T6W"],
        "kwp_dc": [1000, 1000, 800, 600, 800],
        "kwh_capacity": [0, 0, 0, 0, 0],
        "offtaker_type": ["iea_direct"] * 5,
        "tenant_name": [None] * 5,
        "tenant_tier": ["C"] * 5,
        "self_consumption_pct": [0.85] * 5,
        "p50_kwh_yr": [1380000, 1380000, 1104000, 828000, 1104000],
        "p90_kwh_yr": [1242000, 1242000, 993600, 745200, 993600],
        "segment_capex_usd": [660000, 660000, 576000, 534000, 585600],
        "unit_cost_per_kwp": [660, 660, 720, 890, 732],
    })


def _base_assumptions():
    return financial.FinancialAssumptions(
        ltv=0.60,
        interest_rate=0.060,
        tenor_years=12,
        tariff_thb_per_kwh=3.85,
        tariff_escalation_pct=0.0,
        boi_years=8,
    )


def test_model_returns_required_keys():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    required = {
        "cashflow", "epc_usd_m", "tpc_usd_m", "equity_usd_m", "debt_usd_m",
        "total_mwp", "sponsor_irr", "dscr_per_year", "dscr_p90",
        "npv_usd_m", "moic", "payback_years", "y10_exit_irr", "y10_moic",
        "segments",
    }
    assert required.issubset(result.keys())


def test_total_project_cost_includes_soft_costs():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    ratio = result["tpc_usd_m"] / result["epc_usd_m"]
    # Should be ≈ 1.165 (8% dev + 2% fin + 5% conting + 1.5% IDC)
    assert 1.15 < ratio < 1.18


def test_equity_plus_debt_equals_tpc():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    assert abs(result["equity_usd_m"] + result["debt_usd_m"] - result["tpc_usd_m"]) < 0.01


def test_cashflow_year_zero_has_negative_equity():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    y0 = result["cashflow"].loc[result["cashflow"]["year"] == 0].iloc[0]
    assert y0["fcfe_usd"] < 0  # equity invested in year 0


def test_cashflow_spans_25_years():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    years = result["cashflow"]["year"].tolist()
    assert min(years) == 0
    assert max(years) == 25
    assert len(years) == 26  # years 0..25 inclusive


def test_dscr_during_tenor_only():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    # DSCR computed for years 1..tenor (12)
    assert len(result["dscr_per_year"]) == 12


def test_boi_holiday_zeroes_tax():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    cf = result["cashflow"]
    # Years 1-8 (BOI standard) should have zero tax
    tax_holiday_years = cf.loc[cf["year"].between(1, 8), "tax_usd"]
    assert (tax_holiday_years == 0).all()


def test_higher_ltv_increases_sponsor_irr():
    df = _sample_segments()
    low = financial.model(df, _base_assumptions())
    high_assumptions = _base_assumptions()
    high_assumptions.ltv = 0.65
    high = financial.model(df, high_assumptions)
    # More leverage → higher equity IRR (as long as DSCR holds)
    assert high["sponsor_irr"] > low["sponsor_irr"]


def test_zero_tariff_yields_no_revenue():
    df = _sample_segments()
    a = _base_assumptions()
    a.tariff_thb_per_kwh = 0.0
    result = financial.model(df, a)
    cf = result["cashflow"]
    assert (cf.loc[cf["year"] >= 1, "revenue_usd"] == 0).all()


def test_degradation_reduces_revenue_over_time():
    df = _sample_segments()
    result = financial.model(df, _base_assumptions())
    cf = result["cashflow"]
    y1_rev = cf.loc[cf["year"] == 1, "revenue_usd"].iloc[0]
    y25_rev = cf.loc[cf["year"] == 25, "revenue_usd"].iloc[0]
    # 1%/yr degradation over 24 years ≈ -21%
    assert y25_rev < y1_rev * 0.85
    assert y25_rev > y1_rev * 0.70
