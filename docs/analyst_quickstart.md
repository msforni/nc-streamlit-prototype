# Analyst Quickstart — NewCo Scoping Calculator v0.1

For Steven and the analyst running the first end-to-end scoping for Bangplee or Map Ta Phut.

## 30-second summary

1. Install Python 3.11+, run `pip install -r requirements.txt`
2. Run `streamlit run app.py`
3. In the browser sidebar, select **Bangplee** (or MTP)
4. Upload your segment CSV (see format below)
5. Adjust LTV / tariff / BOI in sidebar
6. Click **Run scoping**
7. Read the headline metrics + per-segment table + sensitivity tornado
8. Export results to CSV via the **Export** button

## What "end-to-end" means for v0.1

The prototype implements **Stages 1-7** of the NC-METH-001 canonical pipeline:

| Stage | What it does | Where it happens |
|---|---|---|
| 1 — Intake | Validates your CSV against the schema; flags T1-at-LK/LPH errors, BESS-at-LC warnings | `engine/intake.py` |
| 2 — Sizing | Converts m² → kWp DC using per-typology coefficients (T1: ~7 m²/kWp, T4A: ~9 m²/kWp, etc.) | `engine/sizing.py` |
| 3 — Yield | Applies P50 (1380 kWh/kWp/yr for EEC zone, 1350 for Bangkok, etc.) | `engine/yield_model.py` |
| 4 — CAPEX | Per-typology unit cost × kWp + 16.5% soft costs stack (dev 8%, fin 2%, contingency 5%, IDC 1.5%) | `engine/capex.py` |
| 5 — Offtaker | IEAT-direct vs tenant attribution; per-tier credit haircut (A=100%, B=95%, C=88%, D=75%) | `engine/offtaker.py` |
| 6 — Financial | 25-year cashflow → sponsor IRR, DSCR per year + P90, NPV @ 8%, MOIC, payback, Y10 exit @ 13.5× | `engine/financial.py` |
| 7 — Sensitivity | Tornado: CAPEX ±10/20%, yield ±10%, tariff ±10%, OPEX ±10%, rate ±100bp, BOI 8/13yr, consent 60/80/100% | `engine/sensitivity.py` |

What's NOT in v0.1 (deferred to v0.2+):
- Map UI / GIS — bring your own segment CSV
- PDF IC paper generation
- Multi-user auth + persistence
- LTV optimization solver (manual slider only)

## CSV input format

Minimum required columns:

```
segment_id, estate, typology, area_m2 (or kwp_dc), offtaker_type, self_consumption_pct
```

Full schema: `schemas/segment_csv_schema.json`. Templates: `data/bangplee_template.csv`, `data/mtp_template.csv`.

### Typology cheat sheet

| Typology | What | LC unit cost $/kWp | m²/kWp coefficient |
|---|---|---|---|
| T1 | Industrial rooftop, zero-foundation | 660 | 7.1 |
| T2 | Building rooftop, shallow-pile | 720 | 7.1 |
| T4A | Carport / parking canopy | 890 | 9.1 |
| T4B-DC | Decorative concrete attachment | 810 | 8.0 |
| T6W | Water surface (fixed/floating) | 732 | 7.1 |
| BESS | Battery storage (kWh, not kWp) | 187.5 (per kWh) | n/a |

### Standing input restrictions

- **T1 is INVALID** at Lat Krabang and Lamphun (land-lease estates where IEAT doesn't own the buildings). The engine will hard-fail if you submit T1 at those estates.
- **BESS at Laem Chabang** triggers a warning and the segment is excluded — LC has no BESS by design.
- **`self_consumption_pct`** must be in [0, 1]. Recommend 0.80-0.95 based on operational profile; 0.85 is a reasonable default for industrial estates.
- **Tenant tier** defaults to C if missing or unrecognized. Use A/B/C/D per Annex G grading.

## How to scope a new estate (Bangplee example)

1. Start with `data/bangplee_template.csv`. Replace placeholder rows with real segments from your GIS / asset inventory work.
2. For each segment:
   - `segment_id`: unique ID (e.g., `BP-T1-001`)
   - `typology`: pick from the cheat sheet above
   - `area_m2`: from your polygon shapefile / Drive surface inventory
   - `offtaker_type`: `iea_direct` if IEAT owns the building; `tenant` if a factory tenant occupies it
   - `tenant_name` + `tenant_tier`: if tenant
   - `self_consumption_pct`: estimate from operational profile (e.g., 24/7 factory = 0.90; 5-day office = 0.65)
3. Upload via the Streamlit file uploader.
4. Set sidebar:
   - **LTV**: start at 60% (LC sponsor base); pull down to 52% if DSCR breaches
   - **Interest rate**: 6.0% (EXIM blended) or 5.75% (EXIM standard)
   - **Tenor**: 12 years standard
   - **Tariff**: 3.85 THB/kWh default; override if your ESA negotiation indicates different
   - **BOI**: 8 years standard; 13 years if you have EEC enhancement (note: not yet awarded as of May 2026)
5. Click **Run scoping**.
6. Read outputs:
   - **Sponsor IRR**: target ≥ 15% net LP IRR per Fund I
   - **DSCR P90**: must be ≥ 1.10× (covenant), prefer ≥ 1.30× (lender-sized)
   - **Y10 exit IRR**: 13.5× EBITDA multiple, comparable to LC canonical 14.3%
   - **Tornado**: identifies biggest IRR sensitivities. CAPEX and yield typically dominate.

## Reading the LC validation badge

When `estate == Laem Chabang`, the app runs a ground-truth check against NC-FM-LC-001 v1.0 canonical values (locked in `engine/parameters.LC_CANONICAL`).

- ✅ Green: engine within ±0.5% of canonical. Outputs are trustworthy.
- ⚠ Amber: engine drift detected. Investigate before relying on outputs for new estates.

**Important**: the current `data/lc_v1_segments.csv` is a SYNTHETIC 47-segment fixture whose aggregates approximate the real LC v1.0 register but the segment-level data is invented. For production validation, replace with the real register from `LC_Package/07_Segment_Register/` and the test thresholds will tighten to ±0.5%.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `T1 typology invalid at land-lease estates` | T1 row at Lat Krabang or Lamphun | Use T2 or T4A instead |
| `Missing required columns` | CSV lacks `segment_id`, `estate`, `typology`, `offtaker_type`, or `self_consumption_pct` | Add them |
| `self_consumption_pct out of [0,1]` | You used 85 instead of 0.85 | Convert to decimal |
| `PV segments present but neither 'area_m2' nor 'kwp_dc' column found` | CSV has no sizing data | Add `area_m2` or pre-compute `kwp_dc` |

## When to call for help

- LC validation badge shows ⚠ amber → check `parameters.py` for any unexpected parameter overrides
- Sponsor IRR < 10% on a "good-looking" estate → check tenant_tier defaults (low tier compresses IRR a lot)
- DSCR breaches at sponsor LTV → drop LTV to 52% (lender-sized); if still breaches at 45%, the deal is fundamentally tight, escalate

## What to send back to inform v0.2 scope

After your Bangplee or MTP run:
1. Did the engine return outputs within the same order of magnitude as your manual NC-METH-001 walk-through?
2. Was anything in the UI confusing or missing?
3. Which sensitivities matter most for this estate?
4. What columns or features did you wish for?

Drop notes in `06_Workstreams/NC-SPRINT-001` or as a follow-on memo. v0.2 scope is informed by what you find.

---

**End of analyst quickstart.**
