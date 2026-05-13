# NewCo Investment Scoping Calculator — v0.1

Streamlit prototype implementing Stages 1-7 of the NC-METH-001 canonical pipeline. Analyst uploads a per-segment CSV; system returns IRR, DSCR, MOIC, payback, and sensitivity bands.

**Status**: v0.1 prototype. IEAT-Industrial asset class only. LC v1.0 validated as ground truth.

## Quickstart

```bash
# 1. Clone or download this directory
cd 11_Streamlit_Prototype

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run tests against LC v1.0 ground truth
pytest tests/

# 5. Launch the app
streamlit run app.py
# Opens browser at http://localhost:8501
```

## Using the app

1. In the sidebar, select an estate (LC for canonical validation, Bangplee/MTP for new scoping)
2. Either:
   - Upload your own segment CSV (see `schemas/example_input_lc.csv` for format), OR
   - Use the pre-loaded LC v1.0 fixture, OR
   - Use an empty template from `data/`
3. Adjust debt LTV slider, tariff override (if needed), interest rate
4. Click "Run scoping"
5. Read headline metrics, per-segment table, cashflow chart, sensitivity tornado, LC validation badge

## Inputs

Required CSV columns (see `schemas/segment_csv_schema.json` for full spec):
- `segment_id`, `estate`, `typology` (T1/T2/T4A/T4B-DC/T6W/BESS)
- `area_m2` (for PV) OR `kwh_capacity` (for BESS)
- `offtaker_type` (iea_direct / tenant / mixed)
- `tenant_name`, `tenant_tier` (A/B/C/D per Annex G) if tenant
- `self_consumption_pct` (0-1)

## Outputs

- Total envelope (MWp), EPC ($M), total project cost ($M)
- Sponsor IRR @ 60% LTV / @ 52% LTV (lender-sized)
- DSCR (per-year + P90)
- Payback (blended energy + carbon × 75% delivery)
- Y10 exit IRR + MOIC @ 13.5× EBITDA
- Sensitivity tornado (7 dimensions)
- LC validation diagnostic (if estate == Laem Chabang)

## Engine architecture

See `NC-STREAMLIT-001_v0.1_Architecture.md` in this folder for the full spec. Module map:

| Module | Stage | What it does |
|---|---|---|
| `engine/intake.py` | Stage 1 | Validates CSV schema |
| `engine/sizing.py` | Stage 2 | m² → kWp DC per typology |
| `engine/yield_model.py` | Stage 3 | P50 / P90 by location |
| `engine/capex.py` | Stage 4 | Unit cost × kWp + soft costs |
| `engine/offtaker.py` | Stage 5 | IEAT-direct vs tenant; credit grading |
| `engine/financial.py` | Stage 6 | 25-year cashflow + IRR/DSCR/NPV/MOIC |
| `engine/sensitivity.py` | Stage 7 | Tornado bands |
| `engine/validation.py` | — | LC v1.0 ground-truth check |
| `engine/pipeline.py` | — | Orchestrator |
| `engine/parameters.py` | — | NC-PARAM-001 v1.1.1 values |

## Acceptance criteria

The prototype is successful if:
1. Steven + one analyst can scope Bangplee or MTP end-to-end in under 30 minutes
2. Output IRR is within 1% of the manual NC-METH-001 walk-through for the same inputs
3. `tests/test_lc_ground_truth.py` passes (LC v1.0 outputs match to ±0.5%)
4. Sensitivity tornado is plausible (±50 bps vs NC-FM-LC-001 manual sensitivity)

## Deployment options

See `docs/deployment.md`.

- **Streamlit Cloud** (free tier) — recommended for prototype share
- **Self-host** on AWS / GCP / Cloudflare — for internal-only
- **Local-only** — `streamlit run app.py` on analyst laptop

## Known limitations (v0.1, by design)

- IEAT-Industrial only (no other asset classes)
- No map UI; CSV input only (GIS done upstream)
- No PDF IC paper generation
- No multi-user auth (session-only state)
- No optimization (manual LTV adjustment, no solver)
- Solar carbon @ $10/t T-VER hard-coded midpoint (per Thai ICC Aug 2025)
- BESS pricing $185/kWh midpoint hard-coded

All deferred to v0.2+ per the architecture roadmap.

## Maintenance

- Parameters change → update `engine/parameters.py`, bump version per NC-METH-001 Part F
- Tests must pass before any merge to main
- LC ground-truth test is the single non-negotiable gate

---

**End of README.**
