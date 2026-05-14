"""Canonical parameters from NC-PARAM-001 v1.1.1.

Single source of truth for the engine. When NC-PARAM-001 bumps version,
update PARAM_VERSION and the relevant constants below, then re-run the LC
ground-truth test.

Reference: NewCo_Platform_v1.1_CANONICAL/01_Platform_Spine/
           NC-PARAM-001_v1.1.1_Parameter_Book.md
"""

from __future__ import annotations

from typing import Final

PARAM_VERSION: Final[str] = "1.1.1"
PARAM_DATE: Final[str] = "2026-05-13"

# ============================================================
# §3 — Currency and FX
# ============================================================

FX_THB_USD_MAIN: Final[float] = 35.0        # All NewCo programs (default)
FX_THB_USD_IET: Final[float] = 32.0         # Investment Entity legal/contract only
FX_THB_USD_BMA_LOCKED: Final[float] = 32.0  # BMA RFP only (locked in published procurement)

# ============================================================
# §4 — Tariffs (THB/kWh)
# ============================================================

TARIFF_BMA_RFP: Final[float] = 4.20                       # User-locked
TARIFF_IEAT_LC: Final[float] = 3.85                       # LC v1.0 PPA (flat)
TARIFF_MEA_PEAK: Final[float] = 4.28                      # Reference
TARIFF_MEA_OFF_PEAK: Final[float] = 2.34                  # Reference
TARIFF_MEA_SHOULDER: Final[float] = 3.61                  # Reference
TARIFF_PEA_INDUSTRIAL: Final[float] = 3.88                # Reference
TARIFF_PEA_GOVT_PROGRAM: Final[float] = 4.15              # Treasury / SAT / MOPH template
TARIFF_NON_LC_IEAT_DEFAULT: Final[float] = 3.85           # Default for BP / MTP / others; analyst can override

# Tariff escalation
ESCALATION_IEAT_LC: Final[float] = 0.00                    # LC is flat
ESCALATION_BMA_FRF: Final[float] = 0.00                    # Fixed in RFP
ESCALATION_BMA_MEA_TARIFF: Final[float] = 0.02             # 2%/yr (asymmetry is the value driver)
ESCALATION_GOVT_PROGRAM_EMF: Final[float] = 0.02           # 2%/yr per April 2026 template

# ESA standard mechanics
ESA_DISCOUNT_RATE: Final[float] = 0.08                      # 8%
ESA_DEGRADATION: Final[float] = 0.010                       # 1%/yr (canonical TOPCon; NC-PARAM-001 §11 says 0.5% in §4 mechanics)
ESA_DEAD_BAND: Final[float] = 0.03                          # 3%
ESA_SHORTFALL_FACTOR: Final[float] = 1.0                    # 1.0×

# ============================================================
# §5 — Solar yield (kWh/kWp/yr P50)
# ============================================================

YIELD_BANGKOK_P50: Final[float] = 1_350.0                   # BMA, MOPH, SAT, Treasury baseline
YIELD_EEC_P50: Final[float] = 1_380.0                       # LC, BP, MTP, Bangplee, Bang Chan, Nakhon Luang
YIELD_NORTHERN_P50: Final[float] = 1_300.0                  # Lamphun, Chiang Mai, Lampang
YIELD_SOUTHERN_P50: Final[float] = 1_420.0                  # Songkhla, Rubber City

YIELD_P90_FACTOR: Final[float] = 0.90                       # P90 = P50 × 0.90

# AUDIT-001 OPEN: methodology RES-001 says EEC = 1485, model uses 1380.
# v0.1 uses 1380 (LC v1.0 canonical) to preserve LC ground truth.

# Estate → yield zone mapping
ESTATE_YIELD_ZONE: Final[dict[str, float]] = {
    "Laem Chabang": YIELD_EEC_P50,
    "Bangpoo": YIELD_EEC_P50,
    "Bangplee": YIELD_EEC_P50,
    "Bang Chan": YIELD_EEC_P50,
    "Map Ta Phut": YIELD_EEC_P50,
    "Map Ta Phut Port": YIELD_EEC_P50,
    "Nakhon Luang": YIELD_EEC_P50,
    "Lat Krabang": YIELD_EEC_P50,           # Greater Bangkok / Eastern
    "Samut Sakhon": YIELD_EEC_P50,
    "Sa Kaeo": YIELD_EEC_P50,
    "Phichit": YIELD_BANGKOK_P50,           # Central; closest to Bangkok climate
    "Kaeng Khoi": YIELD_BANGKOK_P50,        # Saraburi
    "Smart Park": YIELD_EEC_P50,
    "Lamphun": YIELD_NORTHERN_P50,
    "Songkhla": YIELD_SOUTHERN_P50,
    "Songkhla-S": YIELD_SOUTHERN_P50,
    "Rubber City": YIELD_SOUTHERN_P50,
}

# ============================================================
# §6 — CAPEX per typology
# ============================================================

# Solar PV TOPCon 610Wp — range; midpoints for v0.1 model.
# Defaults below are LC v1.0 canonical (Annex H). For other estates, multiply by
# a scale factor or analyst override.
CAPEX_PER_KWP_T1: Final[float] = 660.0           # Industrial rooftop, zero-foundation
CAPEX_PER_KWP_T2: Final[float] = 720.0           # Building rooftop, shallow-pile
CAPEX_PER_KWP_T4A: Final[float] = 890.0          # Carport, 3.0m soffit
CAPEX_PER_KWP_T4B_DC: Final[float] = 810.0       # Decorative concrete canopy
CAPEX_PER_KWP_T6W: Final[float] = 732.0          # Water surface fixed

# Soft costs (% of EPC)
SOFT_COST_DEVELOPMENT: Final[float] = 0.08       # 8% dev / soft
SOFT_COST_FINANCING: Final[float] = 0.02         # 2% fin fees
SOFT_COST_CONTINGENCY: Final[float] = 0.05       # 5% contingency
SOFT_COST_IDC: Final[float] = 0.015              # 1-2% typical; midpoint

# Total CAPEX multiplier on EPC
TOTAL_CAPEX_MULTIPLIER: Final[float] = (
    1.0 + SOFT_COST_DEVELOPMENT + SOFT_COST_FINANCING + SOFT_COST_CONTINGENCY + SOFT_COST_IDC
)
# = 1.165 → LC: $25.04M EPC × 1.165 = $29.17M (canonical: $29.16M; rounding)

# BESS
BESS_USD_PER_KWH_LFP: Final[float] = 175.0       # BNEF April 2026
BESS_THERMAL_PREMIUM: Final[float] = 12.5        # midpoint of $10-15
BESS_USD_PER_KWH_FULL: Final[float] = BESS_USD_PER_KWH_LFP + BESS_THERMAL_PREMIUM  # = 187.5
BESS_CYCLE_LIFE: Final[int] = 6_000
BESS_RTE: Final[float] = 0.90
BESS_REFRESH_YEAR: Final[int] = 12

# ============================================================
# §7 — OPEX (THB / MWp / year)
# ============================================================

OPEX_OM_THB: Final[float] = 700_000              # AUDIT-016 OPEN
OPEX_INSURANCE_THB: Final[float] = 300_000
OPEX_LAND_GRID_THB: Final[float] = 200_000
OPEX_SPV_ADMIN_THB: Final[float] = 150_000
OPEX_TOTAL_THB_PER_MWP: Final[float] = (
    OPEX_OM_THB + OPEX_INSURANCE_THB + OPEX_LAND_GRID_THB + OPEX_SPV_ADMIN_THB
)  # = 1,350,000

OPEX_ESCALATION: Final[float] = 0.025            # 2.5%/yr

# ============================================================
# §8 — Carbon
# ============================================================

# Thai ICC Aug 2025 STANDING CORRECTION: solar PV excluded from ITMO/CORSIA.
# Solar clears T-VER domestic only. ITMO route available for EE only.

CARBON_SOLAR_TVER_USD: Final[float] = 10.0       # T-VER domestic midpoint $5-15
CARBON_EE_ITMO_USD: Final[float] = 40.0          # Article 6.2 midpoint $25-55 (cooling/steam/EE only)
CARBON_GS_POA_USD: Final[float] = 15.0           # Gold Standard PoA base case

# Grid emission factor — Principal canonical decision 12 May 2026
GRID_EF_TCO2_PER_MWH: Final[float] = 0.4750      # CANONICAL
GRID_EF_CM_GS_BASELINE: Final[float] = 0.5664    # For GS PoA baseline calc only

# Delivery confidence (discount on carbon revenue)
CARBON_DELIVERY_TIER_1: Final[float] = 1.00      # Registered + active monitoring
CARBON_DELIVERY_TIER_2: Final[float] = 0.90      # Registered, no monitoring history
CARBON_DELIVERY_TIER_3: Final[float] = 0.75      # In-registration (v0.1 default)
CARBON_DELIVERY_TIER_4: Final[float] = 0.50      # Speculative
CARBON_DELIVERY_DEFAULT: Final[float] = CARBON_DELIVERY_TIER_3

# ============================================================
# §9 — BOI
# ============================================================

BOI_STANDARD_TENOR: Final[int] = 8               # Activity 5.2.1 — 8yr CIT exemption
BOI_EEC_ENHANCEMENT_TENOR: Final[int] = 13       # EEC enhancement (under evaluation)
CIT_RATE_THAILAND: Final[float] = 0.20           # 20% standard

# ============================================================
# §10 — Debt
# ============================================================

DEBT_RATE_IEAT_LC: Final[float] = 0.060          # LC blended
DEBT_RATE_EXIM_STANDARD: Final[float] = 0.0575   # 5.75% other EXIM programs
DEBT_TENOR_YEARS: Final[int] = 12
DEBT_GRACE_YEARS: Final[int] = 1

DSCR_TARGET: Final[float] = 1.30
DSCR_COVENANT_MIN: Final[float] = 1.10

# LTV scenarios (per NC-PARAM-001 §12 LC canonical investment summary)
LTV_SPONSOR_BASE: Final[float] = 0.60            # 12.8% IRR
LTV_LENDER_SIZED: Final[float] = 0.52            # 12.2% IRR (execution case)
LTV_CONSERVATIVE: Final[float] = 0.45            # 11.7% IRR
LTV_AGGRESSIVE: Final[float] = 0.70              # BREACHES DSCR at LC

# LTV basis — what the LTV percentage applies to.
# Per NC-FM-LC-001 v1.0 IC and standard PF practice for hard-asset senior debt:
# debt is sized against hard EPC, not total project cost (which includes soft
# costs, development fees, and IDC typically funded by equity).
# Override per asset class via LTV_BASIS_BY_ESTATE below.
# Resolved in 14 May 2026 sprint (NC-SPRINT-002 LC drift escalation): A + C.
LTV_BASIS_EPC: Final[str] = "EPC"
LTV_BASIS_TPC: Final[str] = "TPC"
LTV_BASIS_DEFAULT: Final[str] = LTV_BASIS_EPC

# Per-asset-class override map. Populate as new asset classes are validated
# against ground truth. Keys are estate / asset-class names; lookup is
# case-insensitive in financial.model. Falls back to LTV_BASIS_DEFAULT.
LTV_BASIS_BY_ESTATE: Final[dict[str, str]] = {
    "laem chabang": LTV_BASIS_EPC,
    "lc": LTV_BASIS_EPC,
    # Add other asset classes here as canonical references are established.
    # Example: "bma-buildings": LTV_BASIS_TPC,
}

# ============================================================
# §11 — Returns / operating parameters
# ============================================================

FUND_TARGET_NET_IRR: Final[float] = 0.15
FUND_TARGET_GROSS_IRR: Final[float] = 0.18
HURDLE_RATE: Final[float] = 0.08
CARRIED_INTEREST: Final[float] = 0.20
MANAGEMENT_FEE: Final[float] = 0.02
ASSET_USEFUL_LIFE: Final[int] = 25
ESA_TERM_STANDARD: Final[int] = 20
MODULE_EFFICIENCY_MIN: Final[float] = 0.21

# Exit
EXIT_MULTIPLE_LC_Y10: Final[float] = 13.5        # × EBITDA — canonical LC Y10 exit
EXIT_YEAR: Final[int] = 10

# ============================================================
# §15 — IEAT estate areas (rai)
# ============================================================

ESTATE_AREA_RAI: Final[dict[str, float]] = {
    "Laem Chabang": 3_498,
    "Bangpoo": 5_851,            # OSM-locked 17 Apr 2026, 9.36 km²
    "Lat Krabang": 2_559,        # T1 invalid (land-lease)
    "Sa Kaeo": 660,
    "Samut Sakhon": 1_212,
    "Songkhla": 629,
    "Songkhla-S": 2_180,
    "Map Ta Phut": 8_040,
    "Map Ta Phut Port": 3_156,
    "Phichit": 1_235,
    "Lamphun": 1_846,            # T1 invalid (land-lease)
    "Bangplee": 1_004,
    "Bang Chan": 677,
    "Nakhon Luang": 1_441,
    "Kaeng Khoi": 574,
    "Smart Park": 1_384,         # UMC lapsed — flag
}

# ============================================================
# §14 — Critical standing corrections (architectural)
# ============================================================

T1_INVALID_ESTATES: Final[set[str]] = {"Lat Krabang", "Lamphun"}
BESS_BY_DESIGN_NONE: Final[set[str]] = {"Laem Chabang"}  # LC has no BESS per LC v1.0
SMART_PARK_UMC_LAPSED: Final[bool] = True
PIE_PRIME_DORMANT: Final[bool] = True

# ============================================================
# §12 — LC v1.0 canonical investment summary (used for validation)
# ============================================================

LC_GROUND_TRUTH: Final[dict[str, float]] = {
    "envelope_mwp": 34.59,
    "epc_usd_m": 25.04,
    "total_project_cost_usd_m": 29.16,
    "ppa_thb_kwh": 3.85,
    "p50_yield_kwh_kwp_yr": 1_380.0,
    "opex_thb_per_mwp": 1_350_000,
    "gearing_60_debt_usd_m": 15.02,
    "gearing_60_equity_usd_m": 14.14,
    "interest_rate": 0.060,
    "tenor_years": 12,
    "boi_years": 8,
    "irr_60_ltv": 0.128,
    "irr_52_ltv": 0.122,
    "irr_45_ltv": 0.117,
    "y10_irr_at_135x_exit": 0.143,
    "moic_y10": 3.50,
}

# Acceptance threshold for engine drift vs LC v1.0
LC_DRIFT_THRESHOLD_RELATIVE: Final[float] = 0.005   # 0.5%
LC_DRIFT_THRESHOLD_IRR_BPS: Final[float] = 50       # 50 bps

# Typology kWp coefficients (m² → kWp DC)
# Empirically derived from LC v1.0 segment register; analyst can override per segment.
KWP_PER_M2_BY_TYPOLOGY: Final[dict[str, float]] = {
    "T1": 1.0 / 7.0,       # ~7 m²/kWp industrial rooftop
    "T2": 1.0 / 7.0,       # ~7 m²/kWp building rooftop
    "T4A": 1.0 / 9.0,      # ~9 m²/kWp carport (lower density per m² ground)
    "T4B-DC": 1.0 / 8.0,   # ~8 m²/kWp decorative concrete
    "T6W": 1.0 / 7.0,      # ~7 m²/kWp water surface fixed
}

# Typology → CAPEX lookup
CAPEX_BY_TYPOLOGY: Final[dict[str, float]] = {
    "T1": CAPEX_PER_KWP_T1,
    "T2": CAPEX_PER_KWP_T2,
    "T4A": CAPEX_PER_KWP_T4A,
    "T4B-DC": CAPEX_PER_KWP_T4B_DC,
    "T6W": CAPEX_PER_KWP_T6W,
}

ALLOWED_TYPOLOGIES: Final[set[str]] = {"T1", "T2", "T4A", "T4B-DC", "T6W", "BESS"}
ALLOWED_OFFTAKER_TYPES: Final[set[str]] = {"iea_direct", "tenant", "mixed"}
ALLOWED_TENANT_TIERS: Final[set[str]] = {"A", "B", "C", "D"}

# Tenant tier → credit confidence factor (applied to tenant-attributed revenue)
TENANT_TIER_CREDIT_FACTOR: Final[dict[str, float]] = {
    "A": 1.00,        # Investment-grade equivalent
    "B": 0.95,        # Cross-over
    "C": 0.85,        # Speculative-grade
    "D": 0.65,        # Distressed / unrated
}
DEFAULT_TENANT_TIER: Final[str] = "C"
