"""End-to-end pipeline tests."""

from pathlib import Path

import pandas as pd
import pytest

from engine.pipeline import run


FIXTURE_DIR = Path(__file__).parent.parent / "data"


def test_pipeline_runs_on_lc_fixture():
    df = pd.read_csv(FIXTURE_DIR / "lc_v1_segments.csv")
    result = run(
        df,
        ltv=0.60,
        interest_rate=0.060,
        tenor_years=12,
        tariff_thb_per_kwh=3.85,
        tariff_escalation_pct=0.0,
        boi_years=8,
        estate="Laem Chabang",
    )
    assert result["n_segments"] == 47
    assert 34.0 < result["total_mwp"] < 35.5


def test_pipeline_runs_on_bangplee_template():
    df = pd.read_csv(FIXTURE_DIR / "bangplee_template.csv")
    result = run(
        df,
        ltv=0.60,
        interest_rate=0.060,
        tenor_years=12,
        tariff_thb_per_kwh=3.85,
        tariff_escalation_pct=0.015,
        boi_years=13,  # EEC enhancement
        estate="Bangplee",
    )
    # Sanity: positive envelope, positive cashflows by year 5
    assert result["total_mwp"] > 0
    y5_rev = result["cashflow"].loc[
        result["cashflow"]["year"] == 5, "revenue_usd"
    ].iloc[0]
    assert y5_rev > 0


def test_pipeline_includes_sensitivity():
    df = pd.read_csv(FIXTURE_DIR / "lc_v1_segments.csv")
    result = run(
        df,
        ltv=0.60,
        interest_rate=0.060,
        tenor_years=12,
        tariff_thb_per_kwh=3.85,
        tariff_escalation_pct=0.0,
        boi_years=8,
        estate="Laem Chabang",
    )
    sens = result["sensitivity"]
    assert isinstance(sens, list)
    assert len(sens) >= 7
    dims = {row["dimension"] for row in sens}
    assert "CAPEX ±10%" in dims
    assert "Yield ±10%" in dims
    assert "Tariff ±10%" in dims


def test_invalid_input_raises_value_error():
    bad_df = pd.DataFrame({"segment_id": ["X"], "wrong_column": [1]})
    with pytest.raises(ValueError):
        run(
            bad_df,
            ltv=0.60, interest_rate=0.060, tenor_years=12,
            tariff_thb_per_kwh=3.85, tariff_escalation_pct=0.0,
            boi_years=8, estate="Bangplee",
        )
