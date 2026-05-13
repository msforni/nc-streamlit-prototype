"""Stage 7 — Sensitivity tornado.

Runs the financial model under perturbed inputs and returns IRR deltas (bps)
for each sensitivity dimension. Output drives the tornado chart in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, List

import pandas as pd

from . import capex as capex_mod
from . import financial
from . import offtaker
from . import parameters as P


@dataclass
class SensitivityResult:
    """One row of the tornado chart."""
    label: str
    upside_irr_bps: float       # IRR delta in basis points for the "up" perturbation
    downside_irr_bps: float     # IRR delta in basis points for the "down" perturbation


def tornado(
    df_attributed: pd.DataFrame,
    epc_usd: float,
    total_project_cost_usd: float,
    opex_year1_usd: float,
    base_inputs: financial.FinancialInputs,
    base_equity_irr: float,
) -> List[SensitivityResult]:
    """Run the standard tornado sweep.

    Each dimension perturbs base_inputs (or upstream inputs) and re-runs the
    financial model. Returns IRR deltas vs base case in basis points.
    """
    results: List[SensitivityResult] = []

    def _delta_bps(irr: float) -> float:
        if pd.isna(irr) or pd.isna(base_equity_irr):
            return 0.0
        return float((irr - base_equity_irr) * 10_000.0)

    # 1. CAPEX ±10%
    up_capex_10 = financial.model(
        df_attributed, epc_usd * 1.10, total_project_cost_usd * 1.10,
        opex_year1_usd, base_inputs,
    )
    dn_capex_10 = financial.model(
        df_attributed, epc_usd * 0.90, total_project_cost_usd * 0.90,
        opex_year1_usd, base_inputs,
    )
    results.append(SensitivityResult(
        label="CAPEX ±10%",
        upside_irr_bps=_delta_bps(dn_capex_10.equity_irr),    # lower CAPEX = higher IRR
        downside_irr_bps=_delta_bps(up_capex_10.equity_irr),
    ))

    # 2. CAPEX ±20%
    up_capex_20 = financial.model(
        df_attributed, epc_usd * 1.20, total_project_cost_usd * 1.20,
        opex_year1_usd, base_inputs,
    )
    dn_capex_20 = financial.model(
        df_attributed, epc_usd * 0.80, total_project_cost_usd * 0.80,
        opex_year1_usd, base_inputs,
    )
    results.append(SensitivityResult(
        label="CAPEX ±20%",
        upside_irr_bps=_delta_bps(dn_capex_20.equity_irr),
        downside_irr_bps=_delta_bps(up_capex_20.equity_irr),
    ))

    # 3. Yield ±10% (scale attributed consumption)
    df_up_yield = df_attributed.copy()
    df_up_yield["attributed_consumption_kwh"] *= 1.10
    df_dn_yield = df_attributed.copy()
    df_dn_yield["attributed_consumption_kwh"] *= 0.90
    up_yield = financial.model(df_up_yield, epc_usd, total_project_cost_usd, opex_year1_usd, base_inputs)
    dn_yield = financial.model(df_dn_yield, epc_usd, total_project_cost_usd, opex_year1_usd, base_inputs)
    results.append(SensitivityResult(
        label="Yield ±10%",
        upside_irr_bps=_delta_bps(up_yield.equity_irr),
        downside_irr_bps=_delta_bps(dn_yield.equity_irr),
    ))

    # 4. Tariff ±10%
    up_tariff = replace(base_inputs, tariff_thb_kwh=base_inputs.tariff_thb_kwh * 1.10)
    dn_tariff = replace(base_inputs, tariff_thb_kwh=base_inputs.tariff_thb_kwh * 0.90)
    up_t = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, up_tariff)
    dn_t = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, dn_tariff)
    results.append(SensitivityResult(
        label="Tariff ±10%",
        upside_irr_bps=_delta_bps(up_t.equity_irr),
        downside_irr_bps=_delta_bps(dn_t.equity_irr),
    ))

    # 5. OPEX ±10%
    up_o = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd * 1.10, base_inputs)
    dn_o = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd * 0.90, base_inputs)
    results.append(SensitivityResult(
        label="OPEX ±10%",
        upside_irr_bps=_delta_bps(dn_o.equity_irr),
        downside_irr_bps=_delta_bps(up_o.equity_irr),
    ))

    # 6. Interest rate ±100 bps
    up_r = replace(base_inputs, debt_rate=base_inputs.debt_rate + 0.01)
    dn_r = replace(base_inputs, debt_rate=base_inputs.debt_rate - 0.01)
    up_r_res = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, up_r)
    dn_r_res = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, dn_r)
    results.append(SensitivityResult(
        label="Rate ±100 bps",
        upside_irr_bps=_delta_bps(dn_r_res.equity_irr),
        downside_irr_bps=_delta_bps(up_r_res.equity_irr),
    ))

    # 7. BOI scenarios: 13yr EEC vs 8yr base
    eec_inputs = replace(base_inputs, boi_years=P.BOI_EEC_ENHANCEMENT_TENOR)
    eec_res = financial.model(df_attributed, epc_usd, total_project_cost_usd, opex_year1_usd, eec_inputs)
    results.append(SensitivityResult(
        label="BOI 13yr EEC (vs 8yr base)",
        upside_irr_bps=_delta_bps(eec_res.equity_irr),
        downside_irr_bps=0.0,  # one-sided
    ))

    # 8. Tenant consent: 100% vs 80% vs 60%
    df_80 = offtaker.tenant_consent_factor(df_attributed, consent_pct=0.80)
    df_60 = offtaker.tenant_consent_factor(df_attributed, consent_pct=0.60)
    res_80 = financial.model(df_80, epc_usd, total_project_cost_usd, opex_year1_usd, base_inputs)
    res_60 = financial.model(df_60, epc_usd, total_project_cost_usd, opex_year1_usd, base_inputs)
    results.append(SensitivityResult(
        label="Tenant consent 80% (vs 100%)",
        upside_irr_bps=0.0,  # one-sided downside
        downside_irr_bps=_delta_bps(res_80.equity_irr),
    ))
    results.append(SensitivityResult(
        label="Tenant consent 60% (vs 100%)",
        upside_irr_bps=0.0,
        downside_irr_bps=_delta_bps(res_60.equity_irr),
    ))

    return results


def tornado_to_dataframe(results: List[SensitivityResult]) -> pd.DataFrame:
    """Convert tornado results to a DataFrame for plotly."""
    return pd.DataFrame([
        {
            "Sensitivity": r.label,
            "Downside (bps)": r.downside_irr_bps,
            "Upside (bps)": r.upside_irr_bps,
            "Range (bps)": abs(r.upside_irr_bps - r.downside_irr_bps),
        }
        for r in results
    ])
