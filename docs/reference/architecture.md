# Architecture

**Last updated:** 2026-09-09

v2 layout and data flow. Setup: [contributing.md](../contributing.md). Board details: [board.md](board.md). Catalog vs user state: [catalog-pattern.md](catalog-pattern.md). How this graph was reached: [backend-soul-refactor.md](backend-soul-refactor.md).

---

## Repo map

One product in one repo. **Apps** are how you run it; **domains** are where logic lives. Do not split multi-repo while panel, workers, and MCP share Postgres and `core/`.

| Kind | Location | Role |
|------|----------|------|
| **Apps** | [`apps/`](../../apps/) | Deployables — panel, fetch-worker, role-propagator, mcp |
| **Domains** | [`relocation_jobs/`](../../relocation_jobs/) | Domain packages (catalog, fetch, scrape, …) |
| **Ops** | [`scripts/`](../../scripts/) | Deploy helpers; Docker still calls these paths |
| **UI** | `static/`, `frontend/`, `homepage/` | Panel UI, React board widget, marketing site |

```
apps/panel/run.py
apps/fetch-worker/run.py
apps/role-propagator/          # Go SQS assignment writer
apps/mcp/run.py          # stdio
apps/mcp/run_http.py     # HTTP + OAuth
```

Full table: [apps/README.md](../../apps/README.md).

---

## Data flow

```
relocate.me (country page)
    ↓
build_companies.py       ← careers URL discovery → Postgres catalog
    ↓
v2 fetch (panel) or scrape_jobs.py (CLI)  ← ATS scrape → Postgres catalog
    ↓
web/server.py            ← Flask API (catalog + per-user tracking merge)
    ↓
static/js/ + frontend/   ← UI; React pagination in static/dist/
```

---

## v2 package layout

```
relocation_jobs/
├── catalog/      repo — companies, jobs, sync_company_board_to_catalog
├── positions/    repo + service — apply, reject, not-for-me
├── panel/        relocation board flatten + stats
├── remote/       remote board service + country list (aggregators)
├── fetch/        scheduler (when/what), runner (panel threads), country_runner (semaphore), pipeline (scrape+persist)
├── scrape/       boards/, merge, enrich, aggregator_* 
├── companies/    company CRUD
├── users/        history, applied, entitlements
├── opportunities/ preference + opportunity reads; enqueue refresh
├── broadcast/     freemium peek / consume / capacity meta
├── credits/       promotional/purchased wallet grants + immutable ledger
├── payments/      checkout providers, signed notifications, reconciliation
├── async_jobs/    typed SQS enqueue only (Go consumes)
├── positions/     job tracking status (applied/seen/…)
├── mcp/          Claude Desktop MCP: application prep, tex → PDF (v0)
├── admin/        dashboard aggregates
├── web/          server, routes, deps
├── shared/       board_contract, predicates, coerce, schema
└── db/           v2-only migrations
```

**Layer rule:** SQL only in `*/repo.py`. See [rules.md](rules.md).

---

## Data stores

| Store | Contents |
|-------|----------|
| **Postgres** (`DATABASE_URL`) | Catalog, users, tracking, fetch runs |
| `data/custom_cities.json` | User-added cities (`PANEL_DATA_DIR`) |

---

## Ownership

| Capability | Owner | Writes |
|------------|--------|--------|
| Job ingestion | `fetch/` + `scrape/` | catalog via `catalog/repo.py` |
| Catalog | `catalog/` | companies, matching jobs |
| User prefs / plan | `users/` + `opportunities/service.py` | prefs, plan |
| Credits / payments | `credits/`, `payments/` | wallet, orders |
| Opportunity + role assignment rows | Go `apps/role-propagator` | `user_opportunities`, `position_broadcast_assignments` |
| Consume / peek | `broadcast/` | `consumed_at` on user action |
| Async transport | `async_jobs/enqueue.py` | SQS (or local `ROLE_PROPAGATOR_BIN`) |

Python board/API **reads** assignment state. Board GET does not enqueue. Login, prefs PUT, payment, plan change, and finished fetch jobs enqueue `type=user|country|replace`. Assignment **creation** is Go (`ReconcileSticky` in `apps/role-propagator`). Python `opportunities/reconcile.py` is **test-only**. User actions may mark `consumed_at` on existing rows only (`UPDATE`, no insert). Limits: `users/entitlements.py` (Go reads the same env vars).

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

Board GET does **not** write prefs, enqueue refresh, or insert assignment rows. Empty slots stay empty until login / `PUT /api/preferences` / payment / a finished fetch enqueues Go.

`GET /api/preferences` returns in-memory defaults (`germany`) when no row exists; it does not insert.

`capacity_meta_for_user` may call `credit_balance` (credits own monthly grant). Legacy credit import runs on login, not on board read.

Response: `{ companies, meta, user_stats }`. Default `page_size` = 25.

**Stats:** Full dashboard at `GET /api/admin/panel-stats` (admin only). Board returns lightweight `user_stats`.

**Sort / newest:** [board.md](board.md) — client-side per page; server returns DB order.

---

## Panel UI (client)

| Piece | Location |
|-------|----------|
| Board load / pagination | `static/js/board.js`, `board-view.js`, `api.js` |
| React pagination | `frontend/src/BoardPagination.jsx` → `#board-pagination-root` |
| Company cards | `frontend/src/CompanyCard.jsx`, `static/js/render.js` |
| Job mutations | `static/js/job-board.js` (prefer local updates) |

Layout: **pagination → search → sort/filters → company cards**.

---

## Fetch

```
apps/fetch-worker/run.py          (scripts/fetch_scheduler_worker.py is a Docker shim)
  → fetch/scheduler.main
  → run_scheduled_pass            listing check, then countries
  → run_fetch_cycle               when / which countries
  → runner.run_country_fetch_blocking
       asyncio.run(run_country_fetch) — no panel thread
  → country_runner                asyncio.Semaphore (only concurrency knob)
  → pipeline.fetch_and_persist_company
       load company → scrape → sync_company_board_to_catalog → record attempt
  → scrape/ + catalog/repo.py
```

Package spine: `relocation_jobs.fetch` exports `bootstrap_scheduler`, `run_fetch_cycle`, `start_country_fetch` (lazy; avoid importing scheduler from `__init__`).

After a country or company **run** finishes (`fetch/runner.py`), enqueue `type=country`. Scrape/pipeline/country_runner do not enqueue.

- Config: `FETCH_SCHEDULE_ENABLED`, `FETCH_SCHEDULE_INTERVAL_HOURS`, `FETCH_SCHEDULE_CONCURRENCY`, `FETCH_SCHEDULE_COUNTRIES`
- Cap: `core/ats_constants.MAX_CONCURRENCY`
- Status: `GET /api/fetch/status`
- Panel fire-and-forget only: `start_country_fetch` / `start_company_fetch` (thread + UI poll)

## Async / SQS

Messages (`async_jobs/types.py`): `{type:user,user_id}`, `{type:country,country}`, `{type:replace,...}`.

Producer: `async_jobs/enqueue.py`. Requires `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` or `ROLE_PROPAGATOR_BIN` (raises otherwise). Consumer: `go run ./apps/role-propagator`. Failure: SQS visibility + DLQ (`maxReceiveCount=3`). Ops: [sqs-opportunity-refresh.md](../operations/sqs-opportunity-refresh.md).

## Users, entitlements, payments

- Prefs: `PUT /api/preferences` → `save_preferences_and_refresh` → enqueue user refresh
- Entitlements: `users/entitlements.py` (caps, plan). Admin: `PATCH /api/admin/users/<id>/plan` → enqueue
- Payment success: `payments/service.py` sets plan / grants credits, then enqueues user refresh

---

## v1 (reference only)

Legacy panel on port 5050. Subprocess scrape CLI. Do not extend — use v2 paths above.
