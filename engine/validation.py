"""LC v1.0 ground-truth validation.

If the input estate is Laem Chabang, check engine outputs against the
canonical NC-FM-LC-001 v1.0 values. Drift above threshold = ENGINE DRIFT
warning.

Per NC-METH-001 Annex I acceptance test suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import financial
from . import parameters as P


@dataclass
class ValidationCheck:
    label: str
    expected: float
    actual: float
    threshold: float
    threshold_type: str   # "relative" or "absolute_bps"
    passed: bool
    delta: float


@dataclass
class ValidationReport:
    is_lc: bool
    all_passed: bool
    checks: List[ValidationCheck]
    summary: str

    def to_markdown(self) -> str:
        lines = [f"**LC v1.0 Ground-Truth Validation** — {self.summary}", ""]
        lines.append("| Check | Expected | Actual | Delta | Status |")
        lines.append("|---|---|---|---|---|")
        for c in self.checks:
            status = "✅ PASS" if c.passed else "⚠ DRIFT"
            lines.append(
                f"| {c.label} | {c.expected:.4f} | {c.actual:.4f} | "
                f"{c.delta:+.4f} | {status} |"
            )
        return "\n".join(lines)


def validate_lc(
    estate: str,
    results: financial.FinancialResults,
    results_52_ltv: Optional[financial.FinancialResults] = None,
) -> ValidationReport:
    """Validate engine outputs against LC v1.0 ground truth.

    If estate != Laem Chabang, returns is_lc=False and no checks.
    If estate == Laem Chabang, runs the full LC acceptance test.
    """
    if estate.strip().lower() not in {"laem chabang", "lc"}:
        return ValidationReport(
            is_lc=False,
            all_passed=True,
            checks=[],
            summary="Not Laem Chabang — ground-truth validation skipped.",
        )

    gt = P.LC_GROUND_TRUTH
    checks: List[ValidationCheck] = []

    # Envelope MWp
    checks.append(_relative_check(
        "Envelope (MWp)",
        expected=gt["envelope_mwp"],
        actual=results.envelope_mwp,
        threshold=0.005,  # 0.5%
    ))

    # EPC ($M)
    checks.append(_relative_check(
        "EPC ($M)",
        expected=gt["epc_usd_m"],
        actual=results.epc_usd_m,
        threshold=0.01,  # 1%
    ))

    # Total project cost ($M)
    checks.append(_relative_check(
        "Total project cost ($M)",
        expected=gt["total_project_cost_usd_m"],
        actual=results.total_project_cost_usd_m,
        threshold=0.01,  # 1%
    ))

    # Equity IRR @ 60% LTV
    checks.append(_absolute_bps_check(
        "Equity IRR @ 60% LTV",
        expected=gt["irr_60_ltv"],
        actual=results.equity_irr,
        threshold_bps=P.LC_DRIFT_THRESHOLD_IRR_BPS,  # 50 bps
    ))

    # If 52% LTV results provided, check that too
    if results_52_ltv is not None:
        checks.append(_absolute_bps_check(
            "Equity IRR @ 52% LTV (lender-sized)",
            expected=gt["irr_52_ltv"],
            actual=results_52_ltv.equity_irr,
            threshold_bps=P.LC_DRIFT_THRESHOLD_IRR_BPS,
        ))

    # Y10 exit IRR
    checks.append(_absolute_bps_check(
        "Y10 exit IRR @ 13.5× EBITDA",
        expected=gt["y10_irr_at_135x_exit"],
        actual=results.y10_exit_irr,
        threshold_bps=P.LC_DRIFT_THRESHOLD_IRR_BPS,
    ))

    # MOIC Y10
    checks.append(_relative_check(
        "MOIC Y10",
        expected=gt["moic_y10"],
        actual=results.moic_y10,
        threshold=0.05,  # 5% — MOIC is more sensitive to terminal value assumption
    ))

    all_passed = all(c.passed for c in checks)
    summary = (
        "All checks within threshold ✅" if all_passed
        else "ENGINE DRIFT detected ⚠ — investigate before sponsor sign-off"
    )

    return ValidationReport(
        is_lc=True,
        all_passed=all_passed,
        checks=checks,
        summary=summary,
    )


def _relative_check(label: str, expected: float, actual: float, threshold: float) -> ValidationCheck:
    if expected == 0:
        delta = float("inf") if actual != 0 else 0.0
    else:
        delta = (actual - expected) / expected
    return ValidationCheck(
        label=label,
        expected=expected,
        actual=actual,
        threshold=threshold,
        threshold_type="relative",
        passed=abs(delta) <= threshold,
        delta=delta,
    )


def _absolute_bps_check(label: str, expected: float, actual: float, threshold_bps: float) -> ValidationCheck:
    delta_bps = (actual - expected) * 10_000.0
    return ValidationCheck(
        label=label,
        expected=expected,
        actual=actual,
        threshold=threshold_bps,
        threshold_type="absolute_bps",
        passed=abs(delta_bps) <= threshold_bps,
        delta=delta_bps / 10_000.0,
    )
