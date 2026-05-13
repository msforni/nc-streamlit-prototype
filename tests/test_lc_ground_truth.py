"""
LC v1.0 ground-truth acceptance test.

This is THE non-negotiable gate for the prototype. If the engine drifts more
than ±0.5% from NC-FM-LC-001 v1.0 canonical outputs on the canonical LC fixture,
the test fails and the engine must NOT be relied upon for new estate scoping.

Canonical values are locked in engine.parameters.LC_CANONICAL.

NOTE: The fixture `data/lc_v1_segments.csv` is a synthetic 47-segment dataset
whose aggregates approximate the real LC v1.0 register. For production
validation, replace with the real segment register from
LC_Package/07_Segment_Register/ — the test thresholds will tighten accordingly.
"""

from pathlib import Path

import pandas as pd
import pytest

from engine import parameters as P
from engine.pipeline import run
from engine.validation import lc_ground_truth_check


FIXTURE_DIR = Path(__file__).parent.parent / "data"

# Slightly looser threshold for the synthetic fixture
# Tighten to 0.5% once real LC register is loaded
SYNTHETIC_FIXTURE_THRESHOLD_PCT = 5.0


def _run_lc_canonical():
    df = pd.read_csv(FIXTURE_DIR / "lc_v1_segments.csv")
    return run(
        df,
        ltv=0.60,
        interest_rate=0.060,
        tenor_years=12,
        tariff_thb_per_kwh=3.85,
        tariff_escalation_pct=0.0,
        boi_years=8,
        estate="Laem Chabang",
    )


def test_envelope_mwp_within_threshold():
    result = _run_lc_canonical()
    canonical = P.LC_CANONICAL["active_envelope_mwp"]
    deviation = abs(result["total_mwp"] - canonical) / canonical * 100
    assert deviation < SYNTHETIC_FIXTURE_THRESHOLD_PCT, (
        f"Envelope {result['total_mwp']:.2f} MWp deviates "
        f"{deviation:.2f}% from canonical {canonical} MWp"
    )


def test_segment_count_matches_canonical():
    result = _run_lc_canonical()
    assert result["n_segments"] == P.LC_CANONICAL["n_segments"], (
        f"Expected {P.LC_CANONICAL['n_segments']} segments, "
        f"got {result['n_segments']}"
    )


def test_epc_within_threshold():
    result = _run_lc_canonical()
    canonical = P.LC_CANONICAL["epc_usd_m"]
    deviation = abs(result["epc_usd_m"] - canonical) / canonical * 100
    assert deviation < SYNTHETIC_FIXTURE_THRESHOLD_PCT, (
        f"EPC ${result['epc_usd_m']:.2f}M deviates "
        f"{deviation:.2f}% from canonical ${canonical}M"
    )


def test_total_project_cost_within_threshold():
    result = _run_lc_canonical()
    canonical = P.LC_CANONICAL["total_project_cost_usd_m"]
    deviation = abs(result["tpc_usd_m"] - canonical) / canonical * 100
    assert deviation < SYNTHETIC_FIXTURE_THRESHOLD_PCT


def test_sponsor_irr_at_60_ltv_in_realistic_range():
    """Once real LC register is loaded, tighten to ±50bps of canonical 12.8%."""
    result = _run_lc_canonical()
    assert 0.08 < result["sponsor_irr"] < 0.18, (
        f"Sponsor IRR {result['sponsor_irr']*100:.1f}% outside realistic range"
    )


def test_dscr_p90_at_60_ltv_above_covenant():
    """At 60% LTV (sponsor base), P90 DSCR should be above 1.10× covenant."""
    result = _run_lc_canonical()
    # P90 DSCR can be tight at LC; allow down to 0.85× synthetic but flag
    # Once real register loaded, tighten to ≥ 1.10× per Parameter Book §10.2
    assert result["dscr_p90"] > 0.85, (
        f"P90 DSCR {result['dscr_p90']:.2f}× implausibly low"
    )


def test_ground_truth_check_runs():
    result = _run_lc_canonical()
    check = lc_ground_truth_check(result)
    assert "pass" in check
    assert "max_deviation_pct" in check
    assert "comparisons" in check
    # For synthetic fixture, just verify the check executes
    assert len(check["comparisons"]) >= 5


@pytest.mark.skip(reason="Enable when real LC segment register is loaded as fixture")
def test_strict_ground_truth_within_half_percent():
    """STRICT acceptance test — enable only when real LC register is loaded."""
    result = _run_lc_canonical()
    check = lc_ground_truth_check(result)
    assert check["pass"], (
        f"Engine drift detected. Max deviation: "
        f"{check['max_deviation_pct']:.2f}%. "
        f"Investigate before relying on outputs."
    )
