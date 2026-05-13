"""Pipeline orchestrator.

Chains intake → sizing → yield_model → capex → offtaker → financial → sensitivity → validation.

This is the function the Streamlit UI calls. Single entry point; returns a
dict of all artifacts the UI needs to render results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from . import capex as capex_mod
from . import financial
from . import intake
from . import offtaker
from . import parameters as P
from . import sensitivity
from . import sizing
from . import validation
from . import yield_model


@dataclass
class PipelineResults:
    """Complete output of a pipeline run."""
    df_validated: pd.DataFrame
    intake_warnings: List[str]
    intake_errors: List[str]
    df_sized: pd.DataFrame
    df_yielded: pd.DataFrame
    df_capex: pd.DataFrame
    df_attributed: pd.DataFrame
    epc_usd: float
    total_project_cost_usd: float
    opex_year1_usd: float
    financial_60_ltv: financial.FinancialResults
    financial_52_ltv: Optional[financial.FinancialResults]
    tornado_results: List[sensitivity.SensitivityResult]
    validation_report: validation.ValidationReport
    estate: str


def run(
    df_input: pd.DataFrame,
    inputs: Optional[financial.FinancialInputs] = None,
    also_run_52_ltv: bool = True,
    run_sensitivity: bool = True,
) -> PipelineResults:
    """Run the full canonical pipeline on a segment CSV.

    Caller passes a pandas DataFrame matching the segment schema (see
    `intake.REQUIRED_COLUMNS` + optional). Returns PipelineResults.

    Errors in intake → returned in `intake_errors`; downstream stages skip.
    Warnings in intake → returned in `intake_warnings`; pipeline continues.
    """
    if inputs is None:
        inputs = financial.FinancialInputs()

    # Stage 1 — Intake
    intake_result = intake.validate(df_input)
    if not intake_result.is_valid:
        # Return early with errors; no downstream computation
        return PipelineResults(
            df_validated=intake_result.df,
            intake_warnings=intake_result.warnings,
            intake_errors=intake_result.errors,
            df_sized=pd.DataFrame(),
            df_yielded=pd.DataFrame(),
            df_capex=pd.DataFrame(),
            df_attributed=pd.DataFrame(),
            epc_usd=0.0,
            total_project_cost_usd=0.0,
            opex_year1_usd=0.0,
            financial_60_ltv=_empty_financial_results(),
            financial_52_ltv=None,
            tornado_results=[],
            validation_report=validation.ValidationReport(
                is_lc=False, all_passed=False, checks=[],
                summary="Pipeline did not run — intake errors.",
            ),
            estate="(invalid)",
        )

    df_validated = intake_result.df

    # Stage 2 — Sizing
    df_sized = sizing.compute(df_validated)
    envelope = sizing.envelope_mwp(df_sized)

    # Stage 3 — Yield
    df_yielded = yield_model.compute(df_sized)

    # Stage 4 — CAPEX
    df_capex = capex_mod.compute(df_yielded)
    epc_usd = float(df_capex["segment_epc_usd"].sum())
    total_project_cost_usd = float(df_capex["segment_total_cost_usd"].sum())
    opex_year1_usd = capex_mod.opex_annual_usd(envelope, inputs.fx_thb_usd)

    # Stage 5 — Offtaker
    df_attributed = offtaker.attribute(df_capex)
    if inputs.tenant_consent_pct < 1.0:
        df_attributed = offtaker.tenant_consent_factor(df_attributed, inputs.tenant_consent_pct)

    # Stage 6 — Financial @ 60% LTV (sponsor base)
    fin_60 = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, inputs)

    # Stage 6b — Financial @ 52% LTV (lender-sized) for LC comparison
    fin_52 = None
    if also_run_52_ltv:
        from dataclasses import replace
        inputs_52 = replace(inputs, debt_ltv=P.LTV_LENDER_SIZED)
        fin_52 = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, inputs_52)

    # Stage 7 — Sensitivity (optional; can be expensive)
    tornado = []
    if run_sensitivity:
        tornado = sensitivity.tornado(
            df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd,
            inputs, fin_60.equity_irr,
        )

    # Acceptance check — only meaningful for LC
    estate = df_validated["estate"].mode().iloc[0] if not df_validated.empty else "(unknown)"
    val_report = validation.validate_lc(estate, fin_60, fin_52)

    return PipelineResults(
        df_validated=df_validated,
        intake_warnings=intake_result.warnings,
        intake_errors=intake_result.errors,
        df_sized=df_sized,
        df_yielded=df_yielded,
        df_capex=df_capex,
        df_attributed=df_attributed,
        epc_usd=epc_usd,
        total_project_cost_usd=total_project_cost_usd,
        opex_year1_usd=opex_year1_usd,
        financial_60_ltv=fin_60,
        financial_52_ltv=fin_52,
        tornado_results=tornado,
        validation_report=val_report,
        estate=estate,
    )


def _empty_financial_results() -> financial.FinancialResults:
    """Placeholder for failed runs."""
    return financial.FinancialResults(
        envelope_mwp=0.0, epc_usd_m=0.0, total_project_cost_usd_m=0.0,
        debt_usd_m=0.0, equity_usd_m=0.0,
        year1_revenue_usd_m=0.0, year1_opex_usd_m=0.0, year1_ebitda_usd_m=0.0,
        equity_irr=float("nan"), project_irr=float("nan"),
        npv_at_discount_usd_m=float("nan"), moic_y10=float("nan"),
        payback_years=float("nan"),
        dscr_min=float("nan"), dscr_avg=float("nan"), dscr_breach=False,
        y10_exit_irr=float("nan"),
        cashflow_df=pd.DataFrame(),
    )
