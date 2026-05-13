# v0.2 Scope Decision Framework
## What the second iteration of the Investment Scoping Calculator should and should not include

**13 May 2026 · NC-STREAMLIT-002 (proposed) · DRAFT — finalize after Bangplee + MTP feedback**

This document exists to constrain the natural impulse to over-engineer. Without a forcing function, v0.2 will accrete every wish list item from v0.1 feedback and ship 6 months late. The rule: **v0.2 only adds features that v0.1 feedback proves are blocking.**

---

## Decision-making rule

For every candidate v0.2 feature, ask:

1. **Did Steven or the analyst hit it during their Bangplee/MTP runs?** If no, defer.
2. **Did it block them from getting an IRR/DSCR result?** If no, lower priority.
3. **Is there a cheap workaround in v0.1?** If yes, document the workaround, defer the feature.
4. **Does it require sponsor-grade audit / governance to be safe?** If yes, this is a v1.0 production-portal item, not v0.2.

Only features that clear (1) AND (2) AND fail (3) AND pass (4) belong in v0.2.

---

## Candidate features — prioritized

### Tier 1 — Likely to clear the bar

These are the items most likely to surface from real use:

#### 1. Multi-estate comparison view
- **What**: side-by-side IRR/DSCR/MOIC for Bangplee + MTP + Bangpoo on one screen
- **Why v0.2 not v0.1**: only valuable after you've scoped 2+ estates
- **Effort**: ~1 week — extend the pipeline to handle a list of estate CSVs; add a comparison page to Streamlit
- **Risk**: low

#### 2. LTV solver (max LTV subject to DSCR ≥ 1.30)
- **What**: button that searches for the highest LTV that keeps min DSCR above the covenant
- **Why v0.2 not v0.1**: the manual iteration (try 60, try 55, try 50) is tedious but works
- **Effort**: ~2 days — binary search over LTV; re-run financial model at each candidate
- **Risk**: low

#### 3. Estate-level summary export (CSV or PDF)
- **What**: one-click export of headline metrics + per-segment table + cashflow as a structured file
- **Why v0.2 not v0.1**: current download is cashflow-only; analyst is manually assembling the rest
- **Effort**: ~2 days for CSV; ~1 week for PDF with branding
- **Risk**: low

### Tier 2 — Conditional on feedback

These need explicit feedback signal before being scoped:

#### 4. Map / GIS input UI
- **What**: draw polygons on a map, app extracts m² automatically
- **Why v0.2 not v0.1**: depends on whether analyst struggles with the m² CSV prep step
- **Effort**: ~2-3 weeks — Folium or Mapbox integration; polygon-to-m² calculator; coordinate system handling
- **Risk**: medium. If skipped, current CSV workflow remains functional.

#### 5. Persistence (named scoping sessions)
- **What**: save a Bangplee scoping with all inputs; resume next week with one click
- **Why v0.2 not v0.1**: a refresh wipes session state; analyst re-uploads each time
- **Effort**: ~1 week — back this with a simple SQLite or JSON file store; named session UI
- **Risk**: low

#### 6. Optimization on tariff floor (find tariff that yields target IRR)
- **What**: inverse calculation — given target IRR 15%, what tariff must we negotiate?
- **Why v0.2 not v0.1**: useful for ESA negotiations
- **Effort**: ~2 days
- **Risk**: low

### Tier 3 — Likely to be deferred to v1.0 production portal

These are production-grade, not prototype-grade:

#### 7. Multi-user auth + SSO
- **What**: NewCo Google Workspace login; per-user audit log
- **Why deferred**: requires Path B deploy (Cloudflare Access or equivalent). v0.1 Path A is single-link access.
- **Effort**: ~1 week (Cloudflare config) — but this is hosting, not engine.

#### 8. PDF IC-paper draft generation
- **What**: one-click "draft an IC paper" from the scoping results
- **Why deferred**: needs governance to be useful (cite Parameter Book version, audit register, sponsor sign-off block); production-grade, not prototype
- **Effort**: ~3-4 weeks
- **Risk**: high — sponsor-facing material; needs IC sign-off on template

#### 9. Multi-asset-class support
- **What**: extend beyond IEAT-Industrial to NC-ACP-002+ (Government Program, BMA, MOPH, SAT)
- **Why deferred**: the engine architecture supports it; the typology library and asset class data don't yet
- **Effort**: ~2 weeks per asset class — typology library, ESA terms, BOI mapping, OPEX adjustments

#### 10. Carbon stack sophistication for solar
- **What**: handle T-VER PoA vs project-level; vintage tracking; delivery tier modeling
- **Why deferred**: solar carbon is constrained to T-VER per Thai ICC Aug 2025; revenue is small (~5% of LCC at $10/t); not a v0.2 priority
- **Effort**: ~1 week
- **Risk**: low. Could move to Tier 2 if EE/cooling ITMO modeling becomes priority.

### Tier 4 — Probably never

#### 11. Real-time PEA/MEA tariff API
- **What**: live tariff lookup from utility APIs
- **Why never**: not v0.2 priority. Manual tariff entry from current schedules is fine.

#### 12. Bid-ranking dashboard for procurement
- **What**: compare incoming EPC bids on per-segment basis
- **Why deferred**: that's a procurement tool, not a scoping tool. Different product.

#### 13. Live MAS / RegSummary integrations
- **What**: pulled regulatory data
- **Why deferred**: not the calculator's job.

---

## Anti-features — explicit no's

The v0.2 scope must NOT include:

- ❌ AI-generated IC paper drafting (governance risk; build deterministic v1.0 export first, AI later)
- ❌ Real-time public access ("share the URL on LinkedIn") — internal only
- ❌ Tenant data persistence with PII (creates GDPR / PDPA exposure)
- ❌ Auto-emailing scoping results to sponsors (too easy to send the wrong thing)
- ❌ Anything that mentions a NewCo brand name in user-facing UI (per standing instruction: never external)

---

## Sequencing — if v0.2 is greenlit

Recommended sequence based on feedback patterns observed in similar internal tools:

```
Week 1:   LTV solver (Tier 1 #2) + estate export (Tier 1 #3)
Week 2:   Multi-estate comparison (Tier 1 #1)
Week 3-4: Persistence (Tier 2 #5) OR Map UI (Tier 2 #4), depending on signal
Week 5:   Buffer / polish / regression testing
Week 6:   Deploy v0.2 to Path B (Cloudflare Access)
```

Total: ~6 weeks if Tier 1 only. ~10 weeks if Tier 2 also.

---

## Decision gates

Before any v0.2 build kicks off, three gates:

### Gate 1 — Bangplee + MTP runs complete
- [ ] Steven runs Bangplee end-to-end
- [ ] Analyst runs MTP end-to-end
- [ ] Both feedback logs are aggregated

### Gate 2 — Tier 1 features have feedback evidence
- [ ] At least one of: comparison view, LTV solver, summary export — was requested by name OR was an evident pain point in the runs
- [ ] If NO Tier 1 feature has feedback evidence: v0.1 is "good enough"; defer v0.2 entirely and use the calculator as-is for 1-2 more quarters

### Gate 3 — Engineering capacity
- [ ] Marc has 4-6 weeks of dedicated build time available, OR
- [ ] An analyst with Python skills is identified to own v0.2 build, OR
- [ ] An external dev (Cowork, Claude Code, contract) is available

If no engineering capacity: defer indefinitely. The calculator can run on v0.1 for months.

---

## What gets killed if we don't do v0.2

If v0.2 is never built:
- Calculator remains a single-estate, single-session tool
- Steven scopes one estate per Streamlit session
- LC v1.0 model remains canonical for fund-grade analysis
- Production portal (v1.0) becomes the next leap (not from v0.2 but from v0.1 + lessons learned)

That's fine. v0.1 is a deliberate prototype, not a minimum viable product. The point is to learn what's worth building, not to build the thing.

---

**End of v0.2 scope framework.**
