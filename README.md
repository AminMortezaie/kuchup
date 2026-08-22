# Relocation Jobs

Visa- and relocation-focused job search for backend and software roles in Europe.

Company lists come from [relocate.me](https://relocate.me). Each employer’s ATS is auto-detected; openings are scraped into a **shared Postgres catalog**. A multi-user Flask panel tracks applications. A **Claude Desktop MCP** pipeline prepares tailored LaTeX/PDF resumes and cover letters per position — with **project masters** as a reframe evidence bank. **Interview notes** are a later step: after an invite, per-company prep you store and download — not an input to tailoring.

**Production:** [https://kuchup.com](https://kuchup.com) (AWS EC2 + Cloudflare)  
**Countries:** Germany, Netherlands, UK, Portugal, plus custom countries (e.g. Armenia, Ireland) via the panel.

> **Contributors / docs:** [`docs/contributing.md`](docs/contributing.md) · [`docs/README.md`](docs/README.md) · [`AGENTS.md`](AGENTS.md)

---

## Repo map (one product, one repo)

```
apps/                 deployables — panel, fetch-worker, opportunity-worker, mcp
relocation_jobs/      domains — catalog, positions, panel, fetch, scrape, users, …
frontend/             React board widget → relocation_jobs/static/dist/
homepage/             marketing (Next.js; same-origin /api/public/*)
scripts/              ops helpers + Docker entry paths
docs/                 documentation
tests/                pytest (mirrors relocation_jobs/ domains)
```

| I want to… | Go here |
|------------|---------|
| Run the panel | `python3 apps/panel/run.py` (or `scripts/panel_server.py`) |
| Run a worker | `apps/fetch-worker/`, `apps/opportunity-worker/` |
| Run MCP | `apps/mcp/run.py` (stdio) / `apps/mcp/run_http.py` |
| Change domain logic | `relocation_jobs/<domain>/` |
| Full app list | [`apps/README.md`](apps/README.md) |

Do **not** split into multi-repo: panel, workers, and MCP share Postgres, `core/`, and migrations.

---

## Features

| Area | What you get |
|------|----------------|
| **Company discovery** | Careers URL discovery from relocate.me → Postgres (`build_companies`) |
| **ATS ingestion** | 25 ATS type choices (Greenhouse, Lever, Ashby, Personio, Workable, Workday, …) + Playwright fallback; cached `ats_type` / `ats_url` |
| **Concurrent scrape** | asyncio + httpx (up to **16** workers); relevance include/exclude keywords |
| **Shared catalog + per-user overlay** | Tracking (applied / reject / not-for-me / pin / looking-to-apply) merged at read time |
| **Web panel** | Paginated board (`GET /api/board`, default **25**/page), filters, fetch, add company |
| **Scheduled fetch (prod)** | EC2 Playwright worker every **6 hours** |
| **Application assistant** | Claude Desktop MCP: masters, project masters, gated JD-mirror reframe, validate, PDF (`tectonic`) |
| **Company workspace** | `/company/<country>/<slug>` — positions, CV / cover letter, live PDF preview, board CV/PDF badges |

---

## Quick start

```bash
pip install -r requirements-dev.txt
python3 -m playwright install chromium

cp .env.example .env
# Set DATABASE_URL at minimum (local Postgres is fastest for dev)

PANEL_SCRAPE_ENABLED=1 python3 apps/panel/run.py
# → http://127.0.0.1:5051
# (Docker / ops still use scripts/panel_server.py)
```

On first startup the app creates the Postgres schema. Sign in with **Google** (`GOOGLE_CLIENT_*`). Accounts listed in `PANEL_ADMIN_EMAILS` become admins. Set `PANEL_ALLOW_REGISTER=1` to allow new Google users to self-register.

After editing React UI: `cd frontend && npm run build` → `relocation_jobs/static/dist/board.js`. Hard refresh (`Cmd+Shift+R`) after JS/CSS changes.

---

## Environment

Copy `.env.example` → `.env`. Real hosts/passwords stay in gitignored `.env` / `aws-postgres.env` — this repo is **public**; docs use placeholders only.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | **Required.** Postgres (local or AWS EC2) |
| `REDIS_URL` | Optional country-label cache (`scripts/ec2_redis.sh`); Postgres fallback when unset |
| `PANEL_SECRET_KEY` | Flask session signing |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (required for sign-in) |
| `GOOGLE_REDIRECT_URI` | Optional callback override |
| `PANEL_ADMIN_EMAILS` | Comma-separated Google emails granted admin |
| `PANEL_ADMIN_USER` | Legacy username for scheduler user resolution |
| `PANEL_SCRAPE_ENABLED` | `1` locally for country + company fetch; `0` on slim production panel |
| `PANEL_COMPANY_FETCH_ENABLED` | `1` on EC2 panel for board **Fetch jobs** without enabling country scrape |
| `PANEL_DATA_DIR` | Local data dir for `custom_cities.json` (default `data/`) |
| `PANEL_ALLOW_REGISTER` | Self-service Google registration after first user |
| `PANEL_PUBLIC_BASE_URL` | Panel URL used by MCP “Continue with Google” |
| `MCP_USERNAME` / `MCP_USER_ID` | Panel user for Claude Desktop MCP (default `admin`) |
| `MCP_LATEX_CMD` | LaTeX compiler for PDF (default `tectonic`) |

MCP docs: [mcp-application.md](docs/reference/mcp-application.md) · [company-workspace.md](docs/reference/company-workspace.md).  
AWS Postgres: `./scripts/aws_postgres_migrate.sh sync-sg` after your public IP changes — [ops index](docs/README.md).

---

## Usage

### Web panel

```bash
PANEL_SCRAPE_ENABLED=1 python3 apps/panel/run.py   # → :5051
```

Sign in with Google → select a **single country** → **Fetch** (admin) to scrape. Board: `GET /api/board` (pagination → search → sort/filters). Aggregate stats: admin page / `GET /api/admin/panel-stats` (board only returns lightweight `user_stats`).

Re-scrapes **merge by URL** — fetch dates and tracking are preserved. Jobs gone from an ATS stay as catalog orphans and reappear if you still have tracking.

| Path | Purpose |
|------|---------|
| `/` | Job board |
| `/apply` | Profile, pipeline prompts, **master resumes**, **project masters**, **interview notes** (LaTeX + optional PDF) |
| `/company/<country>/<slug>` | Positions, tailored CV / cover letter, PDF preview, re-render |

**Claude Desktop MCP:** `python3 apps/mcp/run.py` — job context, application queue, masters, project masters, tailored tex/PDF, cover letters, `mark_applied`, add company/position. After an invite: interview notes (`list`/`get`/`save_interview_note`). See [mcp-application.md](docs/reference/mcp-application.md).

### Build company lists

```bash
python3 scripts/build_companies.py netherlands
python3 scripts/build_companies.py uk "Monzo"          # single company
python3 scripts/build_companies.py netherlands --sort-only
```

Sort: city (A–Z) → company size (smallest first) → name (A–Z).

### Scrape jobs

```bash
python3 scripts/scrape_jobs.py --country uk
python3 scripts/scrape_jobs.py --country uk "Monzo"
python3 scripts/scrape_jobs.py --country netherlands --skip-filled
python3 scripts/scrape_jobs.py --country germany --workers 16   # default 16
python3 scripts/scrape_jobs.py --country uk --serial
python3 scripts/scrape_jobs.py --all
```

First run per company: detect + cache ATS. Later runs hit the ATS API directly.

---

## Architecture

```
relocate.me
    → build_companies          → Postgres catalog
    → scrape / v2 fetch        → Postgres catalog
    → web/ (Flask)             → board API (catalog + per-user merge)
    → mcp/                     → tailored tex / PDF / project masters
    → /company/…               → workspace + mark_applied
```

### Data stores

| Store | Contents |
|-------|----------|
| **Postgres** (`DATABASE_URL`) | Catalog, users, tracking, fetch runs, MCP artifacts (masters, projects, applications) |
| **Redis** (`REDIS_URL`) | Optional country-label cache |
| `data/custom_cities.json` | User-added cities (`PANEL_DATA_DIR`) |

### Apps (`apps/`) vs domains (`relocation_jobs/`)

| Kind | Location | Role |
|------|----------|------|
| **Apps** | [`apps/`](apps/) | How you run it — panel, fetch-worker, opportunity-worker, mcp |
| **Domains** | [`relocation_jobs/`](relocation_jobs/) | Business logic — catalog, positions, fetch, scrape, … |

```
catalog/      Postgres company + job reads/writes
positions/    Apply, reject, not-for-me, pin, looking-to-apply
panel/        Board flatten, pagination, filters, stats
fetch/        In-process asyncio country + company fetch
scrape/       ATS boards, merge, enrich, relevance
opportunities/ Personalized board + SQS refresh
mcp/          Claude Desktop MCP — masters, projects, tex → PDF
web/          Flask server + routes
companies/    Company CRUD
users/        Users, applied history, entitlements
admin/        Dashboard aggregates
core/         db, auth, ATS constants, detection
db/           Migrations bootstrap
static/       UI (+ dist/board.js from frontend/)
```

**Layer rule:** SQL only in `*/repo.py`. Details: [architecture.md](docs/reference/architecture.md) · [rules.md](docs/reference/rules.md) · [apps/README.md](apps/README.md).

### Board API

`GET /api/board` — `page`, `page_size` (default 25, max 100), `country`, `q`, filter flags. **Visible-offset** pagination after flatten + filters. “Newest first” is **client-side on the current page**; server returns catalog order. Full flow: [board.md](docs/reference/board.md).

### ATS detection (first run)

```
careers_url
  → 1. KNOWN_ATS override
  → 2. detect_ats_static()
  → 3. detect_ats_via_playwright()   # XHR intercept
  → 4. generic Playwright DOM fallback
```

### Job filtering

Titles must match an **include** keyword and no **exclude** keyword (`INCLUDE_KEYWORDS` / `EXCLUDE_KEYWORDS` in `core/ats_constants.py`; `scrape/relevance.py`).

---

## Testing

```bash
pytest tests -o addopts=                 # v2 suite (~299 collected)
pytest tests/mcp -o addopts=             # MCP / application assistant
pytest tests/test_route_manifest.py -o addopts=
pytest --cov --cov-report=term-missing   # 90% gate on business modules
```

In-memory Postgres mock only — no live ATS or production DB. Contracts: [business-rules.md](docs/reference/business-rules.md).

---

## Deployment (kuchup.com)

One AWS EC2 host: Postgres + Redis + panel + fetch worker + Caddy. Guide: [ec2-panel.md](docs/operations/ec2-panel.md).

| Service | Role |
|---------|------|
| Postgres (`pg`) | Source of truth |
| Redis | Country-label cache when configured |
| Panel (`relocation-panel`) | Gunicorn; slim image; `PANEL_SCRAPE_ENABLED=0`, `PANEL_COMPANY_FETCH_ENABLED=1` |
| Fetch worker (`relocation-fetch-worker`) | Playwright; country scrape every **6h** (concurrency **4**) |
| Caddy | TLS + reverse proxy for kuchup.com / www (raw IP → 404) |
| Cloudflare | DNS; optional orange-cloud + origin lock-down |

```bash
./scripts/ec2_app_deploy.sh deploy      # frontend build, rsync, images, restart
./scripts/ec2_app_deploy.sh sync        # UI / static only
./scripts/ec2_app_deploy.sh status
./scripts/ec2_app_deploy.sh worker-logs
```

Requires gitignored `aws-postgres.env` and deploy SSH key. After laptop IP changes: `./scripts/aws_postgres_migrate.sh sync-sg`.

**Why colocated EC2:** board latency dropped far below Render → remote Postgres. Local scrape (`PANEL_SCRAPE_ENABLED=1`) and the EC2 worker both write the same catalog.

`render.yaml` remains an optional legacy free-tier path (scrape off).

### Local Docker smoke test

```bash
docker build -t relocation-jobs .
docker run --rm -p 8080:10000 \
  -e PORT=10000 \
  -e PANEL_ADMIN_PASSWORD=changeme123 \
  -e DATABASE_URL="postgresql://..." \
  relocation-jobs
```

---

## Development docs

| Topic | Doc |
|-------|-----|
| First 15 minutes | [contributing.md](docs/contributing.md) |
| Architecture | [architecture.md](docs/reference/architecture.md) |
| Coding rules | [rules.md](docs/reference/rules.md) |
| Job buckets | [business-rules.md](docs/reference/business-rules.md) |
| MCP / apply / project masters | [mcp-application.md](docs/reference/mcp-application.md) |
| Agent commands | [CLAUDE.md](CLAUDE.md) |
| Full doc index | [docs/README.md](docs/README.md) |
