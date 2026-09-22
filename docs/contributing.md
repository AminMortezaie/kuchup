# Contributing

**Last updated:** 2026-09-16

Developer setup and where to work. Product usage: [README](../README.md). Doc index: [README.md](README.md).

---

## What this is

A job-search panel for backend/software roles at visa-friendly companies.

```
relocate.me → build_companies.py → Postgres catalog
                              ↓
                    country fetch → scrape ATS boards → Postgres
                              ↓
                    Flask panel + static JS / React widget → per-user tracking
```

**Seeded countries:** Germany, Netherlands, UK, Portugal. Ireland and others can be added from the panel (`custom_countries`).

---

## Current architecture

| Layer | Status | Location |
|------|--------|----------|
| **Apps (deployables)** | How you run it | [`apps/`](../apps/) — [apps/README.md](../apps/README.md) |
| **Python domains** | Active | `relocation_jobs/` |
| **Go assignment writer** | Active | `role_propagator/` |
| **UI** | Shared | `relocation_jobs/static/` + `frontend/` |
| **Postgres** | AWS EC2 Docker (Frankfurt) | `DATABASE_URL` in `.env` |
| **Production** | EC2 kuchup.com | [operations/ec2-panel.md](operations/ec2-panel.md) |

Local panel: **5051**. There is no v1 / port 5050 stack. Detail: [reference/architecture.md](reference/architecture.md).

---

## First 15 minutes

```bash
pip install -r requirements-dev.txt
python3 -m playwright install chromium
cp .env.example .env
# Set DATABASE_URL, PANEL_SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PANEL_ADMIN_EMAILS
# Optional staff admin: PANEL_STAFF_LOGINS (scripts/hash_staff_password.py)
# (use <ELASTIC_IP> from gitignored aws-postgres.env — never commit real hosts/passwords)

PANEL_SCRAPE_ENABLED=1 python3 apps/panel/run.py
# → http://127.0.0.1:5051

pytest tests -o addopts=
```

| Process | Port / role | Entry |
|---------|-------------|--------|
| Panel | 5051 | `apps/panel/run.py` (Docker shim: `scripts/panel_server.py`) |
| Fetch worker | scheduled scrape | `apps/fetch-worker/run.py` |
| Role propagator | SQS assignments | `apps/role-propagator/run.py` |
| MCP stdio / HTTP | Claude / Cursor | `apps/mcp/run.py` / `apps/mcp/run_http.py` |

After JS/CSS: hard refresh (`Cmd+Shift+R`). After React: `cd frontend && npm run build`.

---

## Where to code

### Repo map

| Kind | Location | Role |
|------|----------|------|
| **Apps (deployables)** | [`apps/`](../apps/) | How you run it — [apps/README.md](../apps/README.md) |
| **Domains** | `relocation_jobs/`, `role_propagator/` | Python business logic; Go assignment writer |
| **Ops scripts** | `scripts/` | Deploy helpers + Docker entry paths |
| **UI** | `relocation_jobs/static/`, `frontend/`, `homepage/` | Panel JS, React board, marketing |

```
apps/panel/run.py              Flask panel
apps/fetch-worker/run.py       Scheduled country scrape (HTTP ATS)
apps/playwright-worker/run.py  Chromium boards (jibe / atlassian / hibob)
apps/role-propagator/run.py    Go SQS role assignment writer
apps/mcp/run.py                Claude Desktop MCP (stdio)
apps/mcp/run_http.py           HTTP MCP + OAuth
role_propagator/               Go domain (sticky slots + role assignment)
```

### Domains (`relocation_jobs/`)

```
catalog/      Postgres company + job reads/writes (repo.py)
positions/    Per-user job state (apply, reject, not-for-me)
panel/        flatten_companies, paginated board, stats, filters
fetch/        Country + single-company fetch (in-process asyncio)
scrape/       ATS boards, merge, enrich, relevance
companies/    Company CRUD orchestration
users/        User history, applied dates, entitlements
opportunities/ Personalized board + queue matching
broadcast/    Freemium peek / consume / capacity
credits/      Wallet + ledger
payments/     NOWPayments checkout
mcp/          Claude / Cursor MCP — application prep, tex → PDF
admin/        Dashboard aggregates
web/          Flask server, routes, deps
shared/       predicates, coerce, schema helpers
db/           migrations
```

**Rules:** [reference/rules.md](reference/rules.md) — SQL **only** in `*/repo.py`.

### Domain (`role_propagator/`)

Go assignment writer (sticky company slots + free-tier job picks). Run via `python3 apps/role-propagator/run.py`.

### Client

- Board: `GET /api/board` — [reference/board.md](reference/board.md)
- Layout: pagination → search → sort/filters → company cards
- After job mutations: local updates in `job-board.js`, not full reload
- React bundle: `frontend/` → `npm run build` → `relocation_jobs/static/dist/board.js`

### Do not touch without asking

- AWS infra (`scripts/aws_postgres_migrate.sh`, security groups)
- Production cutover / DNS
- **Do not commit** unless explicitly asked

---

## Database

- **Prod + dev:** AWS EC2 Postgres — [operations/aws-postgres.md](operations/aws-postgres.md)
- **After IP change:** `./scripts/aws_postgres_migrate.sh sync-sg`
- **Tests:** in-memory Postgres mock only — never hit live DB or ATS

---

## Fetch & scrape

Production fetch is a light HTTP image plus an opt-in Chromium sidecar:

| Image | Playwright | Role |
|-------|------------|------|
| Slim panel (`Dockerfile.ec2`) | No | HTTP API, company-fetch without country scrape (`PANEL_COMPANY_FETCH_ENABLED=1`) |
| Light fetch worker (`Dockerfile.ec2-worker`) | No | 6-hour HTTP country scrape (`FETCH_WORKER_KIND=http`, cgroup **512m**) |
| Playwright sidecar (`Dockerfile.ec2-worker-playwright`) | Yes | Opt-in (`DEPLOY_PLAYWRIGHT_WORKER=1`); `jibe` / `atlassian` / `hibob` (cgroup **640m**) |

Default deploy runs `apps/fetch-worker/run.py` only. Browser boards use `apps/playwright-worker/run.py`.

- Country fetch: in-process asyncio (`fetch/country_runner.py`)
- ATS scrape cap: `MAX_CONCURRENCY` 16 (`core/ats_constants.py`)
- Production scheduler: `FETCH_SCHEDULE_CONCURRENCY=2` (do not raise on `t4g.micro` without watching RSS)
- Timeouts: `FETCH_COMPANY_TIMEOUT_SECONDS=300`, `FETCH_COUNTRY_TIMEOUT_SECONDS=2700`, `PLAYWRIGHT_BOARD_TIMEOUT_SECONDS=90`
- Live state: `fetch_runs` + `GET /api/fetch/status`
- CLI: `apps/fetch-worker/run.py`, `scripts/build_companies.py` for batch/offline

---

## Tests

| Command | Scope |
|---------|--------|
| `pytest tests -o addopts=` | Default application suite |
| `pytest tests/test_route_manifest.py -o addopts=` | Fast API route check |
| `pytest -m scrape -o addopts=` | Scraper + board coverage (not in default CI) |
| `./scripts/run_ci_tests.sh` | Same gate as GitHub Actions (`not scrape` + coverage) |
| `go test ./role_propagator` | Go assignment writer |

Job-state changes: read [reference/business-rules.md](reference/business-rules.md) first.

`seed_country()` must sync the full fixture — see [archive/catalog-seed-test-failure.md](archive/catalog-seed-test-failure.md).

---

## Standards (agents)

| Resource | When |
|----------|------|
| [reference/rules.md](reference/rules.md) | Any `relocation_jobs/` or `tests/` edit |
| [reference/business-rules.md](reference/business-rules.md) | Job tracking / panel buckets |
| [docs/README.md](README.md) | Where a topic lives |

---

## Known open items

1. Board read-model / cursor pagination — [proposals/board-read-model-proposal.md](proposals/board-read-model-proposal.md)
2. SQS for per-user fetch/PDF (opportunity SQS already live) — [proposals/multi-user-scaling-proposal.md](proposals/multi-user-scaling-proposal.md)
3. Persist wrong-location hides as `job_tracking` rows — [backlog.md](backlog.md)
4. Deep board pages still rescan catalog from the start
