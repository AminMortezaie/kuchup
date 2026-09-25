# Architecture

**Last updated:** 2026-09-16

Layout and data flow as of 2026-09. Setup: [contributing.md](../contributing.md). Board details: [board.md](board.md). Catalog vs user state: [catalog-pattern.md](catalog-pattern.md). How this graph was reached: [backend-soul-refactor.md](../archive/backend-soul-refactor.md).

---

## Repo map

One product in one repo. **Apps** are how you run it; **domains** are where logic lives. Do not split multi-repo while panel, workers, and MCP share Postgres and `core/`.

| Kind | Location | Role |
|------|----------|------|
| **Apps** | [`apps/`](../../apps/) | Deployables — panel, fetch-worker, playwright-worker, role-propagator, mcp |
| **Domains** | [`relocation_jobs/`](../../relocation_jobs/), [`role_propagator/`](../../role_propagator/) | Python domains (catalog, fetch, scrape, …); Go assignment writer |
| **Ops** | [`scripts/`](../../scripts/) | Deploy helpers; Docker still calls these paths |
| **UI** | `relocation_jobs/static/`, `frontend/`, `homepage/` | Panel UI, React board widget, marketing site |

```
apps/panel/run.py
apps/fetch-worker/run.py
apps/playwright-worker/run.py
apps/role-propagator/run.py    # Go SQS assignment writer
apps/mcp/run.py          # stdio
apps/mcp/run_http.py     # HTTP + OAuth
role_propagator/               # Go domain (assignment writes)
```

Full table: [apps/README.md](../../apps/README.md).

---

## Data flow

```
relocate.me (country page)
    ↓
build_companies.py       ← careers URL discovery → Postgres catalog
    ↓
fetch-worker (Playwright) / panel company-fetch  ← ATS scrape → Postgres catalog
    ↓
web/server.py            ← Flask API (catalog + per-user tracking merge)
    ↓
relocation_jobs/static/js/ + frontend/   ← UI; React pagination in static/dist/
```

---

## Package layout

```
relocation_jobs/
├── catalog/       repo — companies, jobs, sync_company_board_to_catalog
├── positions/     repo + service — apply, reject, not-for-me
├── panel/         relocation board flatten + stats
├── remote/        remote board service + country list (aggregators)
├── fetch/         scheduler (when/what), runner, country_runner (semaphore), pipeline
├── scrape/        boards/, merge, enrich, aggregator_*
├── companies/     company CRUD
├── users/         history, applied, entitlements
├── opportunities/ preference + opportunity reads; enqueue refresh
├── broadcast/     freemium peek / consume / capacity meta
├── credits/       promotional/purchased wallet grants + immutable ledger
├── payments/      checkout providers, signed notifications, reconciliation
├── async_jobs/    typed SQS enqueue only (Go consumes)
├── mcp/           Claude / Cursor MCP: application prep, tex → PDF
├── admin/         dashboard aggregates
├── web/           server, routes, deps
├── shared/        board_contract, predicates, coerce, schema
└── db/            migrations
```

**Layer rule:** SQL only in `*/repo.py`. See [rules.md](rules.md).

---

## Data stores

| Store | Contents |
|-------|----------|
| **Postgres** (`DATABASE_URL`) | Catalog, users, tracking, fetch runs. Panel uses `psycopg_pool.ConnectionPool` (`min_size=2`, `max_size=8` per gunicorn worker). |
| `data/custom_cities.json` | User-added cities (`PANEL_DATA_DIR`) |

---

## Ownership

| Capability | Owner | Writes |
|------------|--------|--------|
| Job ingestion | `fetch/` + `scrape/` | catalog via `catalog/repo.py` |
| Catalog | `catalog/` | companies, matching jobs |
| User prefs / plan | `users/` + `opportunities/service.py` | prefs, plan |
| Credits / payments | `credits/`, `payments/` | wallet, orders |
| Opportunity + role assignment rows | Go `role_propagator/` | `user_opportunities`, `position_broadcast_assignments` |
| Consume / peek | `broadcast/` | `consumed_at` on user action |
| Async transport | `async_jobs/enqueue.py` | SQS (or local `ROLE_PROPAGATOR_BIN`) |

Python board/API **reads** assignment state. Board GET does not enqueue. Login, prefs PUT, payment, plan change, and finished fetch jobs enqueue `type=user|country|replace`. Assignment **creation** is Go (`ReconcileSticky` in `role_propagator/`). Python `opportunities/reconcile.py` is **test-only**. User actions may mark `consumed_at` on existing rows only (`UPDATE`, no insert). Limits: `users/entitlements.py` (Go reads the same env vars).

---

## Panel read path

**Main board:** `GET /api/board` → `opportunities.service.resolve_board_opportunity_scope` → `panel/board.load_catalog_board_page` → `broadcast.service.apply_capacity_to_board_page`.
**Remote board:** `GET /api/remote/board` (same flatten; no relocation opportunity keys). See [board.md](board.md).

1. Load catalog for **selected country only**
2. Load per-user tracking scoped to that country
3. Merge tracking onto catalog jobs at read time
4. Route each job to one bucket: `jobs`, `rejected_jobs`, or `not_for_me_jobs`
5. Reinject orphans per [business-rules.md](business-rules.md)
6. Apply panel filters + search; paginate with **visible offset**

Board GET does **not** enqueue refresh or insert assignment rows. Empty slots stay empty until login / payment / a finished fetch enqueues Go.

`capacity_meta_for_user` may call `credit_balance` (credits own monthly grant). Legacy credit import runs on login, not on board read.

Response: `{ companies, meta, user_stats }`. Default `page_size` = 25.

**Stats:** Full dashboard at `GET /api/admin/panel-stats` (admin only). Board returns lightweight `user_stats`.

**Sort / newest:** [board.md](board.md) — client-side per page; server returns DB order.

---

## Panel UI (client)

| Piece | Location |
|-------|----------|
| Board load / pagination | `relocation_jobs/static/js/board.js`, `board-view.js`, `api.js` |
| React pagination | `frontend/src/BoardPagination.jsx` → `#board-pagination-root` |
| Company cards | `frontend/src/CompanyCard.jsx`, `relocation_jobs/static/js/render.js` |
| Job mutations | `relocation_jobs/static/js/job-board.js` (prefer local updates) |

Layout: **pagination → search → sort/filters → company cards**.

---

## Fetch

```
Go HTTP worker (Dockerfile.ec2-worker, CMD /fetch-scheduler)
  → open fetch_runs row
  → fetch_http_work (one row per HTTP company)
  → goroutine pool (FETCH_HTTP_POOL_SIZE, max 16) + ats_scrape parsers
  → fetch_http_results (status ok | empty | error; jobs JSON when ok/empty)
  → finalize fetch run

Python merge follower (scripts/fetch_merge_consumer.py on panel image)
  → poll fetch_http_results where merge_processed_at IS NULL
  → ok/empty: process_company / merge_matching_jobs / enrich (no board HTTP)
  → error: fetch_problem only (no merge)

Playwright sidecar (apps/playwright-worker/run.py)
  → Python fetch/scheduler (browser ATS only)
```

Panel one-company fetch still uses Python `scrape/board.py` adapters. Package spine: `relocation_jobs.fetch` exports merge consumer helpers in `go_results.py` and `merge_consumer.py`.

Production images:

| Image | Playwright | Env |
|-------|------------|-----|
| Slim panel (`Dockerfile.ec2` target `panel`) | No | `PANEL_SCRAPE_ENABLED=0`, `PANEL_COMPANY_FETCH_ENABLED=1`. No Tectonic |
| MCP (`Dockerfile.ec2` target `mcp`) | No | Panel layers plus Tectonic for PDF render |
| Light fetch worker (`Dockerfile.ec2-worker`) | No | Go `/fetch-scheduler`; `FETCH_HTTP_POOL_SIZE`; no Python in image |
| Merge follower (panel image) | No | Polls `fetch_http_results`; only writer of `matching_jobs` for scheduled HTTP runs |
| Playwright sidecar (`Dockerfile.ec2-worker-playwright`) | Yes | Opt-in (`DEPLOY_PLAYWRIGHT_WORKER=1`); `FETCH_WORKER_KIND=playwright`; `jibe` / `atlassian` / `hibob` |

Playwright-only ATS boards need the sidecar or a local scrape (`PANEL_SCRAPE_ENABLED=1`). The default EC2 worker is HTTP-only and skips those ATS types so an empty board does not close jobs.

- Config: `FETCH_SCHEDULE_ENABLED`, `FETCH_SCHEDULE_INTERVAL_HOURS`, `FETCH_HTTP_POOL_SIZE`, `FETCH_SCHEDULE_COUNTRIES`, `FETCH_WORKER_KIND` (`http` / `playwright` / `all` on Playwright worker only)
- ATS scrape cap: `core/ats_constants.MAX_CONCURRENCY` (16)
- Timeouts (`fetch/timeouts.py`): `FETCH_COMPANY_TIMEOUT_SECONDS=300`, `FETCH_COUNTRY_TIMEOUT_SECONDS=2700`, `PLAYWRIGHT_BOARD_TIMEOUT_SECONDS=90`
- Memory caps: [ec2-panel.md](../operations/ec2-panel.md#worker-memory-caps)
- Status: `GET /api/fetch/status`
- Panel fire-and-forget only: `start_country_fetch` / `start_company_fetch` (thread + UI poll)

## Async / SQS

Messages (`async_jobs/types.py`): `{type:user,user_id}`, `{type:country,country}`, `{type:replace,...}`.

Producer: `async_jobs/enqueue.py`. Requires `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` or `ROLE_PROPAGATOR_BIN` (raises otherwise). Consumer: `python3 apps/role-propagator/run.py`. Failure: SQS visibility + DLQ (`maxReceiveCount=3`). Ops: [sqs-opportunity-refresh.md](../operations/sqs-opportunity-refresh.md).

## Users, entitlements, payments

- Entitlements: `users/entitlements.py` (caps, plan). Admin: `PATCH /api/admin/users/<id>/plan` → enqueue
- Payment success: `payments/service.py` sets plan / grants credits, then enqueues user refresh

---

## History

v1 (port 5050 / subprocess scrape CLI) is gone — [parity.md](../archive/parity.md). Ownership refactor: [backend-soul-refactor.md](../archive/backend-soul-refactor.md).
