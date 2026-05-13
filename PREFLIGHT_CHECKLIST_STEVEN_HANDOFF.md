# Pre-Flight Checklist — Steven Handoff
## Before the calculator goes to Steven + one analyst for the Bangplee or MTP end-to-end run

**13 May 2026 · v0.1 prototype · NC-STREAMLIT-001**

This is the explicit list of items to verify before exposing the calculator to anyone beyond Marc. Read top to bottom. If any item is unchecked, fix it first.

---

## 1. Local execution verification

- [ ] Pull the prototype to a local Python 3.10+ environment
- [ ] `pip install -r requirements.txt` completes without error
- [ ] `pytest tests/test_intake.py -v` — all 16 tests pass
- [ ] `pytest tests/test_financial.py -v` — all 7 tests pass
- [ ] `pytest tests/test_pipeline.py -v` — all 5 tests pass
- [ ] `pytest tests/test_lc_ground_truth.py -v` — all tests pass at the shipped threshold (10% relative; 200 bps IRR). If FULL canonical 47-segment register is in place, tighten thresholds to 0.5% / 50 bps and re-run.
- [ ] `streamlit run app.py` opens the UI without console errors
- [ ] Upload `schemas/example_input_lc.csv` → headline metrics render; cashflow chart renders; tornado renders if enabled
- [ ] Upload `data/lc_v1_segments.csv` → LC validation diagnostic appears (PASS or DRIFT)
- [ ] Try an invalid input (e.g., manually edit a row to set typology = `T1` and estate = `Lat Krabang`) → red error banner appears, pipeline does not run

---

## 2. Canonical fixture decision

The shipped `data/lc_v1_segments.csv` is a **17-row representative subset** of the LC canonical 47-segment register. Two paths:

### Path 2a — Ship as is (recommended for week-1 feedback)
- Keep the 17-row fixture
- Document in README that the LC ground-truth test uses a wider tolerance
- Steven and analyst run on Bangplee/MTP, where the fixture is irrelevant
- Replace with full register before tightening to canonical 0.5%/50 bps thresholds

### Path 2b — Swap in full register before deploy
- Open `LC_Package/07_Segment_Register/` in Drive
- Export the canonical segment register to CSV matching the schema in `schemas/segment_csv_schema.json`
- Save as `data/lc_v1_segments.csv` (overwriting the subset)
- Tighten thresholds in `tests/test_lc_ground_truth.py` to `0.005` relative and `50` bps absolute
- Re-run `pytest tests/test_lc_ground_truth.py -v` — must pass before deploy

Pick one. For v0.1, Path 2a is fine.

---

## 3. Parameter verification

The engine encodes NC-PARAM-001 v1.1.1 values in `engine/parameters.py`. Spot-check:

- [ ] `FX_THB_USD_MAIN = 35.0` — matches Parameter Book §3
- [ ] `TARIFF_BMA_RFP = 4.20` — matches RFP user-lock
- [ ] `TARIFF_IEAT_LC = 3.85` — matches LC PPA
- [ ] `GRID_EF_TCO2_PER_MWH = 0.4750` — matches Marc's 12 May 2026 canonical decision
- [ ] `BESS_USD_PER_KWH_FULL = 187.5` (175 + 12.5 thermal) — matches BNEF April 2026
- [ ] `CARBON_SOLAR_TVER_USD = 10.0` — Thai ICC Aug 2025 standing correction (no ITMO for solar)
- [ ] `LC_GROUND_TRUTH["irr_60_ltv"] = 0.128` — matches NC-FM-LC-001 v1.0 canonical
- [ ] `T1_INVALID_ESTATES = {"Lat Krabang", "Lamphun"}` — matches §14 point 5
- [ ] `BESS_BY_DESIGN_NONE = {"Laem Chabang"}` — matches §14 point 6

If any of these has drifted from the Parameter Book, fix `parameters.py` and re-run the LC ground-truth test before deploy.

---

## 4. Deployment path selection

- [ ] **Path A — Streamlit Community Cloud (free, public URL, ~10 min)**: best for v0.1 feedback gathering. Risk: any URL holder can scope.
- [ ] **Path B — Self-hosted VM + Cloudflare Access (~2-3 hr, $5-20/mo)**: real auth, audit logs. Use when prototype graduates.
- [ ] **Path C — Cowork**: TBD on Cowork's persistent web-service support.

**Recommended for first-week feedback: Path A.**

See `docs/deployment.md` for step-by-step instructions for each path.

---

## 5. Handoff package to Steven

Send Steven a single message with:

- [ ] Link to the running app (Streamlit Cloud URL or local instructions)
- [ ] Link to `docs/analyst_quickstart.md` (or paste contents inline)
- [ ] One sample template (`data/bangplee_template.csv` or `data/mtp_template.csv`)
- [ ] Expected time commitment: 30 min for first end-to-end run
- [ ] What feedback you want, specifically:
  - Time-to-IRR (does it really take 30 min or longer)?
  - Which inputs are obvious, which are confusing?
  - What headline metric was missing that you wanted?
  - Did the sensitivity tornado answer the question you actually had?
  - What would you do differently next time?

Don't over-prompt. The point of v0.1 is to discover what's wrong by watching Steven use it, not to confirm a prior thesis.

---

## 6. Feedback capture mechanism

- [ ] Create a Google Doc or Notion page titled `NC-STREAMLIT-001 v0.1 Feedback Log`
- [ ] Three sections: (a) bugs, (b) missing features, (c) confusing UX
- [ ] Steven + analyst add notes as they run
- [ ] Review after each Bangplee + MTP run
- [ ] Aggregate into v0.2 scope decision

---

## 7. What NOT to do at the v0.1 stage

- ❌ Don't start building v0.2 features in parallel. Let v0.1 feedback drive scope.
- ❌ Don't add auth, persistence, or fancy infra until validated need.
- ❌ Don't add carbon revenue logic for solar — Thai ICC Aug 2025 standing correction means solar = T-VER only.
- ❌ Don't expose the URL beyond Marc + Steven + 1 named analyst. Wider distribution waits for v0.2.
- ❌ Don't claim the calculator "replaces" the LC v1.0 financial model. It's a scoping tool, not a fund-grade model. The LC model remains canonical until the engine clears full LC ground-truth at 0.5%/50 bps.

---

## 8. What to do if the LC ground-truth test fails

If `pytest tests/test_lc_ground_truth.py` fails after a parameter or code change:

1. **Don't commit the change.** Roll back and reproduce on the previous green state to confirm regression.
2. **Identify the source of drift**:
   - Did NC-PARAM-001 actually change? If yes, the failure is expected; document the new LC canonical value.
   - Did the methodology (NC-METH-001) change? If yes, same.
   - Did a calculation in `engine/` change? If yes and methodology hasn't moved, you've introduced a bug.
3. **Document in the audit register** (`02_Methodology/Annex_J_Audit_Register.md`) before merging.
4. **Re-validate downstream**: update LC v1.0 financial model only if the engine drift is methodology-driven, not bug-driven.

---

## 9. Versioning at first deploy

- [ ] `engine/__init__.py` `__version__ = "0.1.0"`
- [ ] `engine/__init__.py` `__param_book_version__ = "1.1.1"`
- [ ] Git tag at first deploy: `streamlit-v0.1.0`
- [ ] Commit message format: `[engine|ui|tests|docs] short description`

---

## 10. Ready-to-deploy gate

All boxes above checked → safe to send the URL to Steven.

**End of pre-flight checklist.**
