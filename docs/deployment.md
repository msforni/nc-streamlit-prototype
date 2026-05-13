# Deployment — NewCo Scoping Calculator v0.1

Three deployment paths from easiest to most production-grade.

## Path A — Local-only (analyst laptop)

Best for: Steven + one analyst doing the first end-to-end run. No external dependencies. Free.

```bash
# 1. Clone or download this directory
cd 11_Streamlit_Prototype

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify tests pass
pytest tests/ -v
# Expected: all tests pass (LC ground-truth test runs in synthetic mode)

# 5. Run the app
streamlit run app.py

# 6. Open http://localhost:8501 in browser
```

**Pro**: Zero infrastructure. Data never leaves the analyst's machine.
**Con**: Not shareable. Can't run scoping as a team workflow.

## Path B — Streamlit Cloud (free tier)

Best for: prototype share with Steven + an extended trial circle.

1. Push the prototype directory to a private GitHub repo (e.g., `newco/scoping-calculator-prototype`)
2. Sign in at https://share.streamlit.io with your GitHub account
3. Click "New app" → select repo → branch `main` → main file `app.py`
4. Wait ~2 minutes for the first build
5. Get a public-or-restricted URL like `https://newco-scoping.streamlit.app`

**Pro**: Free. Auto-rebuilds on Git push. No infrastructure management.
**Con**: Free tier is community-tier (rate-limited, slept if idle). Not suitable for sensitive inputs since the URL is technically public-discoverable.

**Security note**: don't put LC v1.0 real segment data in the GitHub repo if you go this route. Keep the canonical fixture as synthetic. Real estate data flows through file upload at session time.

## Path C — Self-host (recommended for internal-only production)

Best for: making it the team's daily tool.

### Option C.1 — Cloudflare Workers + Pages (simplest paid)

1. Deploy app as a Docker container to Cloudflare Workers (or Fly.io, Railway, Render)
2. Front it with Cloudflare Access for SSO authentication
3. Custom domain like `scoping.newco-internal.example`

Estimated cost: $0-20/month depending on traffic.

### Option C.2 — AWS / GCP

Best for: integration with broader NewCo data infrastructure later. Container on ECS / Cloud Run. SSO via Cognito or Workspace.

Estimated cost: $20-100/month depending on traffic.

### Dockerfile (for any container deployment)

Create `Dockerfile` at the prototype root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t newco-scoping .
docker run -p 8501:8501 newco-scoping
```

## Authentication considerations

The v0.1 prototype has no built-in auth. For any deployment beyond a single analyst's laptop, layer authentication:

- **Cloudflare Access** (recommended): SSO via Google Workspace or other IdP; per-app authorization rules; free for up to 50 users
- **Streamlit Cloud Teams** (paid tier): adds basic SSO at $250/month
- **OAuth2 Proxy** in front of container: free if self-hosting, requires more config

Per NC-OPS-001 v1.1 §9, this prototype is internal-only — never publish a public unauthenticated URL with real estate data.

## Updating the prototype

To roll out a new version:

1. Update code in this directory
2. Run tests: `pytest tests/ -v` — all must pass
3. Commit and push to repo (if Path B or C)
4. If Path B: Streamlit Cloud auto-rebuilds in ~2 min
5. If Path C: redeploy container (CI/CD or manual `docker push` → restart)

Bump the version in `engine/__init__.py` `__version__` for tracking.

## Monitoring

For v0.1 prototype, formal monitoring is overkill. For Path C deployments:
- Streamlit's own `/_stcore/health` endpoint for uptime checks
- Capture errors via `st.error()` already in app.py
- Log file rotation via Docker logging driver

For v0.2+, consider:
- Sentry for error tracking
- Plausible or PostHog for usage analytics (privacy-respecting)
- Anthropic-hosted via Cowork integration if Cowork's Drive scope expands

## Backups & data retention

The v0.1 prototype is stateless — there's nothing to back up beyond the code itself (Git is the backup). Uploaded segment CSVs are session-only and discarded on browser close.

If you add persistence in v0.2 (e.g., "save my scoping" feature), then:
- Use SQLite for single-instance deployments
- Use Postgres + managed backups for multi-instance
- Encryption at rest is non-negotiable for real estate data

## Performance expectations

The prototype is fast — pipeline runs in <1 second for typical 50-segment estates. The slowest step is the sensitivity tornado (9 dimensions × pipeline re-run), which adds ~5-10 seconds. v0.2 could parallelize sensitivity for sub-second tornado.

Memory footprint: ~200 MB per Streamlit session. A small container (512 MB - 1 GB RAM) handles 5-10 concurrent users.

## Known v0.1 deployment limitations

- No HTTPS by default (Path A is HTTP localhost). Always front with HTTPS in production.
- No rate limiting. Add at the Cloudflare / load balancer layer.
- No structured logging. Streamlit prints to stdout; capture via container logging.
- No metrics endpoint. Add Prometheus-style `/metrics` in v0.2 if needed.

---

**End of deployment runbook.**
