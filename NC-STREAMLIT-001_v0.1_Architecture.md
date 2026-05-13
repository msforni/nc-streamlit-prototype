# NewCo Investment Scoping Calculator — Architecture
## Streamlit prototype for the canonical pipeline (v0.1 design spec)

**13 May 2026 · Internal · NC-STREAMLIT-001 v0.1**

---

## 1. Purpose

This Streamlit prototype implements Stages 1-7 of the NC-METH-001 canonical pipeline (Part B) in executable Python, exposed via a web UI. Analyst uploads a per-segment CSV; system returns IRR / DSCR / MOIC / payback + sensitivity bands. The intent is to demonstrate that the platform engine — the moat — can scope a new estate in hours rather than weeks.

**Scope of v0.1**: IEAT-Industrial asset class only (NC-ACP-001 v1.1). Single estate at a time. LC v1.0 as the validation ground truth. Successor scopes (multi-asset-class, multi-program, multi-geography) follow the Phase 3 roadmap in the Charter.

**Out of scope for v0.1**: map UI / GIS, PDF IC paper generation, multi-user auth, persistence beyond session state, optimization passes (e.g., LTV solver).

---

## 2. Reference architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI Layer                       │
│  app.py — sidebar config, file upload, results display          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Engine Pipeline                           │
│  engine/pipeline.py — orchestrates Stages 1-7                   │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │intake  │ │sizing  │ │yield   │ │capex   │ │finance │
   │.py     │ │.py     │ │.py     │ │.py     │ │.py     │
   └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
        ▲           ▲           ▲           ▲           ▲
        │           │           │           │           │
        └───────────┴─────parameters.py─────┴───────────┘
                    (loads NC-PARAM-001 v1.1.1)
```

### Module breakdown

| Module | Purpose | Maps to NC-METH-001 |
|---|---|---|
| `parameters.py` | Loads all canonical parameters from NC-PARAM-001 v1.1.1 (FX, tariffs, yield, CAPEX, OPEX, carbon, BOI, debt). Single source of truth for the engine. | Parameter Book §3-§11 |
| `intake.py` | Validates segment CSV schema; parses typology codes; classifies estate | Part B Stage 1 (geographic intake) |
| `sizing.py` | Per-segment kWp DC sizing from typology coefficients | Part B Stage 2 (capacity sizing) |
| `yield_model.py` | P50 / P90 yield per segment, per location | Part B Stage 3 (yield) + Part D yield |
| `capex.py` | Per-typology unit cost × kWp + soft costs + financing fees + contingency + IDC | Part B Stage 4 (CAPEX) + Annex H |
| `offtaker.py` | IEAT-direct vs tenant-attributed allocation; per-tenant credit grading | Part B Stage 5 + Annex G |
| `financial.py` | 25-year cashflow model → IRR / DSCR / NPV / MOIC / payback / Y10 exit | Part B Stage 6 + Part D financing |
| `sensitivity.py` | Tornado: CAPEX ±10/20%, yield ±10%, tariff ±10%, OPEX ±10%, rate ±100bp, BOI scenarios, tenant consent | Part B Stage 7 + acceptance tests |
| `validation.py` | LC v1.0 ground-truth check; fails build if outputs deviate >0.5% | Annex I acceptance tests |

### Data flow

```
CSV upload (per-segment)
   │
   ▼
intake.validate(df) → df_validated
   │
   ▼
sizing.compute(df_validated) → df_sized          [kWp DC per segment]
   │
   ▼
yield_model.compute(df_sized) → df_yielded       [P50/P90 kWh/yr per segment]
   │
   ▼
capex.compute(df_yielded) → df_with_capex        [$/kWp per typology + soft costs]
   │
   ▼
offtaker.attribute(df_with_capex) → df_attributed [tenant or IEAT-direct]
   │
   ▼
financial.model(df_attributed, debt_params, tariff) → financials
   │   {IRR, DSCR (per year), NPV, MOIC, payback, Y10 exit IRR}
   │
   ▼
sensitivity.tornado(financials, params) → sensitivity_bands
   │
   ▼
UI displays:
  - Headline metrics (IRR / DSCR / MOIC / payback)
  - Per-segment table
  - Annual cashflow chart
  - Sensitivity tornado
  - "Compare to LC v1.0" diagnostic
```

---

## 3. Input schema — segment CSV

Required columns (validated by `intake.py`):

| Column | Type | Required | Description |
|---|---|---|---|
| `segment_id` | string | yes | Unique identifier (e.g., `LC-T6W-03`) |
| `estate` | string | yes | Estate name (e.g., `Laem Chabang`, `Bangpoo`, `Bangplee`) |
| `typology` | string | yes | One of: `T1`, `T2`, `T4A`, `T4B-DC`, `T6W`, `BESS` |
| `area_m2` | float | yes (PV) | Available surface area in m² |
| `kwh_capacity` | float | yes (BESS) | BESS capacity in kWh |
| `kwp_dc` | float | optional | If pre-computed; otherwise derived from `area_m2` × typology coefficient |
| `offtaker_type` | string | yes | One of: `iea_direct`, `tenant`, `mixed` |
| `tenant_name` | string | conditional | Required if `offtaker_type` is `tenant` or `mixed` |
| `tenant_tier` | string | conditional | `A` / `B` / `C` / `D` per Annex G; required if `tenant` |
| `self_consumption_pct` | float | yes | 0-1 (e.g., 0.85 for 85%) |
| `notes` | string | optional | Free-text |
| `suitability_score` | int | optional | 0-4 composite per Annex G Section 3.4 |

**Validation rules**:
1. `typology` must be from the allowed set
2. `T1` typology + `estate` in `{Lat Krabang, Lamphun}` → ERROR (T1 invalid at land-lease estates)
3. `BESS` typology + `estate` == `Laem Chabang` → WARNING (LC has no BESS by design)
4. `self_consumption_pct` must be in `[0, 1]`
5. If `offtaker_type == 'tenant'` and `tenant_tier` is missing → WARNING (assumes tier C)
6. Sum of segment kWp must be ≤ programme-level pipeline (~531 MWp across 13 estates)

---

## 4. Output spec

### 4.1 Headline metrics (top of results page)

| Metric | Format | Computed by |
|---|---|---|
| Total envelope | `XX.XX MWp / N segments` | sizing.py |
| EPC | `$XX.XM` | capex.py |
| Total project cost | `$XX.XM` | capex.py (= EPC × ~1.17) |
| P50 annual generation | `XX,XXX MWh/yr` | yield_model.py |
| Sponsor IRR @ 60% LTV | `XX.X%` | financial.py |
| Sponsor IRR @ 52% LTV (lender-sized) | `XX.X%` | financial.py |
| DSCR P90 | `X.XX×` | financial.py |
| Payback (blended) | `XX.X years` | financial.py |
| Y10 exit IRR @ 13.5× EBITDA | `XX.X% / MOIC X.XX×` | financial.py |

### 4.2 Per-segment table

Sortable DataFrame with columns: `segment_id, typology, kwp_dc, p50_kwh_yr, unit_cost_per_kwp, segment_capex, offtaker_type, tenant_name, sc_pct, year1_revenue, contribution_to_npv`.

### 4.3 Annual cashflow chart

Line chart, x-axis = years 0-25, four traces:
- Revenue (blue)
- OPEX (slate)
- Debt service (amber, descending after Y12)
- Free cash flow to equity (teal, the bottom line)

### 4.4 Sensitivity tornado

Horizontal bar chart, x-axis = IRR delta from base case (bps), one bar per sensitivity dimension:
- CAPEX +10% / -10%
- Yield +10% / -10%
- Tariff +10% / -10%
- OPEX +10% / -10%
- Interest rate +100 bps / -100 bps
- BOI 13yr EEC enhancement vs 8yr base
- Tenant consent 100% / 80% / 60%

### 4.5 LC validation diagnostic

If `estate == 'Laem Chabang'`, run hard-coded comparison against NC-FM-LC-001 v1.0 canonical outputs:
- Envelope 34.59 MWp ± 0.1
- EPC $25.04M ± 1%
- Total project cost $29.16M ± 1%
- Equity IRR @ 60% LTV 12.8% ± 50 bps
- Equity IRR @ 52% LTV 12.2% ± 50 bps

If any deviation exceeds threshold → display ⚠ ENGINE DRIFT warning. This is the acceptance test from NC-METH-001 Annex I.

---

## 5. Tech stack

| Layer | Choice | Why |
|---|---|---|
| UI framework | Streamlit 1.40+ | Fast prototyping; Python-native; analyst-friendly |
| Data | pandas 2.x | Standard tabular |
| Numerics | numpy, numpy-financial | IRR / NPV via `numpy_financial.irr`, `numpy_financial.npv` |
| Plotting | plotly 5.x | Interactive charts; better than matplotlib for dashboard UX |
| Validation | pydantic 2.x or jsonschema | Type-safe input schema |
| Testing | pytest | Aligns with Annex I |
| Deployment | Streamlit Cloud (free tier) OR Anthropic-hosted via Cowork OR self-host on AWS/GCP | Free tier suffices for prototype |

### Dependencies (requirements.txt)

```
streamlit>=1.40
pandas>=2.0
numpy>=1.26
numpy-financial>=1.0
plotly>=5.18
pydantic>=2.5
openpyxl>=3.1
pytest>=8.0
```

---

## 6. File layout

```
11_Streamlit_Prototype/
├── README.md
├── requirements.txt
├── app.py                      # Main Streamlit entry point
├── engine/
│   ├── __init__.py
│   ├── parameters.py           # Loaded from NC-PARAM-001 v1.1.1
│   ├── intake.py               # CSV schema validation
│   ├── sizing.py               # Stage 2 — kWp DC
│   ├── yield_model.py          # Stage 3 — P50/P90
│   ├── capex.py                # Stage 4 — cost stack
│   ├── offtaker.py             # Stage 5 — attribution + credit
│   ├── financial.py            # Stage 6 — cashflow + IRR/DSCR
│   ├── sensitivity.py          # Stage 7 — tornado
│   └── validation.py           # LC ground-truth check
├── schemas/
│   ├── segment_csv_schema.json
│   └── example_input_lc.csv
├── data/
│   ├── lc_v1_segments.csv      # Canonical LC 47-segment input
│   ├── bangplee_template.csv   # Empty template for Bangplee scoping
│   └── mtp_template.csv        # Empty template for Map Ta Phut scoping
├── tests/
│   ├── __init__.py
│   ├── test_intake.py
│   ├── test_pipeline.py
│   ├── test_financial.py
│   └── test_lc_ground_truth.py  # The acceptance test
└── docs/
    ├── analyst_quickstart.md
    └── deployment.md
```

---

## 7. Validation strategy

The prototype is validated against LC v1.0 (NC-FM-LC-001) as the canonical ground truth. The validation flow:

1. **Unit tests** (`tests/`): each module's functions tested in isolation against hand-computed expected values
2. **Pipeline integration test** (`tests/test_lc_ground_truth.py`): runs the full pipeline on `data/lc_v1_segments.csv` and checks outputs against NC-FM-LC-001 v1.0 to ±0.5%
3. **Streamlit smoke test**: app.py loads without error, file upload + scope works on the LC fixture
4. **Acceptance criteria for "Steven + analyst use end-to-end"**:
   - Upload a new estate's segment CSV (Bangplee or MTP)
   - System returns headline metrics within 30 seconds
   - Output matches manual NC-METH-001 walk-through to within 1% on IRR

---

## 8. Known limitations of v0.1

These are deliberately deferred to v0.2 / v0.3 / production portal:

1. **No map UI** — Phase 3a deliverable. v0.1 takes a CSV; the user is responsible for the GIS work to produce per-segment polygons → m².
2. **No PDF IC paper generation** — Phase 3a deliverable.
3. **No persistence** — session state only. Refreshing the page loses input.
4. **No multi-user auth** — single-user local or shared link. Production needs SSO.
5. **No optimization** — the LTV solver (e.g., "find max LTV that keeps DSCR ≥ 1.30") is manual. User changes inputs, sees outputs.
6. **No carbon stack for solar** — solar credits at T-VER domestic $5-15/t per Thai ICC Aug 2025; the model uses a hard-coded $10/t midpoint for v0.1. EE/cooling ITMO sophistication deferred.
7. **No BESS sizing optimization** — BESS input is via the CSV `kwh_capacity` column directly; the engine doesn't optimize.
8. **Single asset class** — IEAT-Industrial only. NC-ACP-002+ extension requires typology-library swap; framework supports it but data not loaded.

---

## 9. Success criteria

v0.1 is successful if:

1. ✅ Steven and one analyst can scope Bangplee (or MTP) end-to-end without help
2. ✅ Output IRR is within 1% of the manual NC-METH-001 walk-through for the same inputs
3. ✅ Time-to-IRR for a new estate is under 30 minutes (vs. weeks of bespoke modeling)
4. ✅ The LC v1.0 ground-truth test passes
5. ✅ The sensitivity tornado is plausibly accurate (±50 bps vs. manual sensitivity in NC-FM-LC-001)

If yes → v0.2 scope discussion (map UI, persistence, multi-estate comparison).
If partial → identify the gap and patch in v0.1.x patches.

---

## 10. Open design questions

These will need analyst input during build:

1. **Self-consumption rates**: are tenant-specific values available, or do we use estate-level averages? v0.1 takes per-segment `self_consumption_pct` from CSV but documentation defaults may be needed.
2. **Tenant credit grading at Bangplee/MTP**: do we have per-tenant ratings yet, or assume tier C across the board? v0.1 needs a default.
3. **Tariff at non-LC IEAT estates**: NC-PARAM-001 §4 has 3.85 for LC but says "Other IEAT estates may negotiate different escalation per individual ESAs." v0.1 needs a default; suggest 3.85 with a UI override field.
4. **BESS pricing**: $175/kWh + thermal premium $10-15/kWh per Parameter Book §6.4 — use $185 midpoint for v0.1 or expose as parameter?

These don't block the build; flag and proceed with reasonable defaults.

---

**End of NC-STREAMLIT-001 v0.1 architecture.**
