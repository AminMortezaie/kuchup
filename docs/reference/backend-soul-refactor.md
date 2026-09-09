# Backend soul refactor (2026-09-09)

**Commit:** [`ce61287`](https://github.com/AminMortezaie/kuchup/commit/ce6128763b5586e115149f30737978ee128e4447) on `main`  
**Shipped:** EC2 panel + fetch worker + `relocation-role-propagator` (deploy verdict `all_ok`)  
**Living call graph:** [architecture.md](architecture.md)  
**Product rules:** [entitlements-and-opportunities.md](entitlements-and-opportunities.md) · queue ops: [sqs-opportunity-refresh.md](../operations/sqs-opportunity-refresh.md)

This is the record of what moved. Architecture.md is the current map; do not treat this page as the runtime source of truth.

---

## Why

Behavior was distributed. Following one operation meant opening unrelated packages: fetch scraped *and* enqueued opportunity refresh; board GET wrote prefs, marked bootstrap, and imported credit usage; Python both created assignment rows and consumed them; enqueue could silently no-op.

The refactor did **not** add a framework, CQRS, DI, schema change, or frontend. It made the **existing** call graph match ownership:

| Soul | Owner | Does |
|------|--------|------|
| Fetch | `apps/fetch-worker` → `fetch/scheduler` → `country_runner` | When / what to scrape; persist catalog |
| Panel reads | `GET /api/board` | Scope + flatten + peek. No writes. |
| Assignment **create** | Go `apps/role-propagator` | `user_opportunities`, `position_broadcast_assignments` |
| Assignment **consume** | Python `broadcast/repo.mark_assignment_consumed` | `UPDATE consumed_at` on an existing row |
| Limits | `users/entitlements.py` | Caps / plan. Go reads the same env vars. |
| Queue | `async_jobs/enqueue.py` | Typed SQS (or local `ROLE_PROPAGATOR_BIN`). No Python consumer. |

---

## Before vs after

### Fetch

**Before:** `apps/fetch-worker/run.py` used `runpy` into the Docker script. The script owned CLI. Pipeline injected a `process_company` closure into `service.fetch_company`, then enqueued opportunity refresh. Scheduler started a **panel thread** and `join`ed it. Listing check ran inside `run_fetch_cycle`. Concurrency knobs lived in several places (`concurrency=8` on the company client).

**After:**

```
apps/fetch-worker/run.py          (scripts/fetch_scheduler_worker.py is a 5-line Docker shim)
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

Enqueue `type=country` happens after a **finished run** in `fetch/runner.py` (country or company worker). Pipeline and `country_runner` do not import `async_jobs`. Panel UI still uses `start_country_fetch` / `start_company_fetch` (thread + poll) only.

### Board / prefs GET

**Before:** `resolve_board_opportunity_scope` wrote default prefs, enqueued user refresh, and marked bootstrap. `GET /api/preferences` could insert. `capacity_meta_for_user` imported legacy credit usage.

**After:** Board / jobs / remote GET only read. `visible_preferences()` returns in-memory `germany` defaults when no row exists. Prefs + enqueue stay on login (`login_or_register_google` / `ensure_dev_login`), `PUT /api/preferences`, plan change, and payment. Legacy credit import (`import_month_usage`) runs on login (still gated by `usage_migration_done`). `credit_balance` monthly grant stays on board meta — that is credits’ invariant, not assignment ownership.

### Assignments

**Before:** `mark_assignment_consumed` did `INSERT … ON CONFLICT` and could invent rows. Python `refresh_user_opportunities` wrote sticky slots. `ensure_company_assignments` ran on board peek.

**After:** Python consume is `UPDATE` only; missing row → `False`, no insert. Production never calls `ensure_company_assignments` or `replace_user_opportunities` (SQL moved to [`tests/helpers/seed.py`](../../tests/helpers/seed.py)). Touch path: load → replacement candidate exists? → spend credit → enqueue `type=replace` → refund if enqueue failed. Runtime sticky is Go `ReconcileSticky`. Python `opportunities/reconcile.py` is **test-only**.

### Async

**Before:** SQS **or** inline Python handlers **or** silent `{reason: no_writer}`.

**After:** SQS (production) or `ROLE_PROPAGATOR_BIN` (local/tests). Neither configured → `RuntimeError`. Types stay `user` / `country` / `replace`. Consumer is only Go.

---

## Size

| | Count |
|--|------:|
| Files in `ce61287` | 60 |
| Lines added | 1,902 |
| Lines removed | 836 |
| Net | **+1,066** |

Most of the addition is the new Go app (`apps/role-propagator/`, **932** lines including tests, Dockerfile, `go.mod`/`go.sum`). Python domain code is a net **delete** of dual write paths.

---

## Files changed (line counts)

`+` / `-` are `git show --numstat` for `ce61287`.

### New — Go assignment writer

| File | + | − | What |
|------|--:|--:|------|
| [`apps/role-propagator/main.go`](../../apps/role-propagator/main.go) | 223 | 0 | SQS poll + `--once` / `--user` / `--country` / `--replace` CLI |
| [`apps/role-propagator/store.go`](../../apps/role-propagator/store.go) | 356 | 0 | Postgres load + write slots and assignments |
| [`apps/role-propagator/assign.go`](../../apps/role-propagator/assign.go) | 151 | 0 | `ReconcileSticky` + pick jobs |
| [`apps/role-propagator/assign_test.go`](../../apps/role-propagator/assign_test.go) | 106 | 0 | Sticky unit tests |
| [`apps/role-propagator/go.mod`](../../apps/role-propagator/go.mod) / [`go.sum`](../../apps/role-propagator/go.sum) | 84 | 0 | Go 1.25 module |
| [`apps/role-propagator/Dockerfile`](../../apps/role-propagator/Dockerfile) | 12 | 0 | Alpine image, `ENTRYPOINT role-propagator` |

### Deleted — dual path / unused

| File | − | Why |
|------|--:|-----|
| [`relocation_jobs/async_jobs/dispatch.py`](../../relocation_jobs/async_jobs/dispatch.py) | 59 | Python SQS consumer |
| [`relocation_jobs/async_jobs/handlers.py`](../../relocation_jobs/async_jobs/handlers.py) | 15 | Inline reconcile when SQS unset |
| [`scripts/opportunity_sqs_worker.py`](../../scripts/opportunity_sqs_worker.py) | 48 | Python worker entry |
| [`apps/opportunity-worker/run.py`](../../apps/opportunity-worker/run.py) | 15 | Deployable shim for that worker |
| [`relocation_jobs/fetch/ports.py`](../../relocation_jobs/fetch/ports.py) | 40 | Protocols nobody needed |
| [`relocation_jobs/broadcast/capacity.py`](../../relocation_jobs/broadcast/capacity.py) | 23 | Unused capacity helper module |

### Fetch soul

| File | + | − | What |
|------|--:|--:|------|
| [`relocation_jobs/fetch/scheduler.py`](../../relocation_jobs/fetch/scheduler.py) | 44 | 23 | Real `main()`, `run_scheduled_pass` (listing check sibling), blocking country fetch |
| [`relocation_jobs/fetch/runner.py`](../../relocation_jobs/fetch/runner.py) | 86 | 42 | `run_country_fetch_blocking` without thread; enqueue after a finished run; `asyncio.wait_for` timeout |
| [`relocation_jobs/fetch/pipeline.py`](../../relocation_jobs/fetch/pipeline.py) | 24 | 44 | Linear load → scrape → persist → record attempt; **no enqueue** |
| [`relocation_jobs/fetch/service.py`](../../relocation_jobs/fetch/service.py) | 52 | 29 | `start_company_attempt` / `finish_company_attempt` (attempt rules stay here) |
| [`relocation_jobs/fetch/__init__.py`](../../relocation_jobs/fetch/__init__.py) | 15 | 0 | Lazy export of scheduler/runner spine |
| [`relocation_jobs/fetch/country_runner.py`](../../relocation_jobs/fetch/country_runner.py) | 0 | 4 | Dropped opportunity enqueue |
| [`relocation_jobs/fetch/state.py`](../../relocation_jobs/fetch/state.py) | 0 | 9 | Removed `wait_for_fetch_thread` |
| [`relocation_jobs/scrape/company.py`](../../relocation_jobs/scrape/company.py) | 22 | 28 | `Callable` instead of deleted ports |
| [`apps/fetch-worker/run.py`](../../apps/fetch-worker/run.py) | 4 | 3 | Calls `scheduler.main` (no `runpy`) |
| [`scripts/fetch_scheduler_worker.py`](../../scripts/fetch_scheduler_worker.py) | 2 | 31 | Docker shim only |

### Reads are reads / assignment consume

| File | + | − | What |
|------|--:|--:|------|
| [`relocation_jobs/opportunities/service.py`](../../relocation_jobs/opportunities/service.py) | 16 | 83 | `visible_preferences`; board scope is read-only; deleted Python rematch |
| [`relocation_jobs/opportunities/repo.py`](../../relocation_jobs/opportunities/repo.py) | 1 | 28 | Removed `replace_user_opportunities` from production |
| [`relocation_jobs/broadcast/repo.py`](../../relocation_jobs/broadcast/repo.py) | 13 | 125 | Consume is `UPDATE` only; create helpers gone |
| [`relocation_jobs/broadcast/service.py`](../../relocation_jobs/broadcast/service.py) | 27 | 37 | Peek does not insert; touch spends then enqueues `replace`; import usage on login path |
| [`relocation_jobs/core/auth.py`](../../relocation_jobs/core/auth.py) | 43 | 2 | Login writes prefs, imports usage, enqueues |
| [`relocation_jobs/web/routes/preferences.py`](../../relocation_jobs/web/routes/preferences.py) | 2 | 2 | GET uses `visible_preferences` |
| [`relocation_jobs/web/routes/admin.py`](../../relocation_jobs/web/routes/admin.py) | 3 | 4 | Plan change still enqueues (no Python write) |
| [`relocation_jobs/payments/service.py`](../../relocation_jobs/payments/service.py) | 3 | 3 | Payment success still enqueues |
| [`relocation_jobs/async_jobs/enqueue.py`](../../relocation_jobs/async_jobs/enqueue.py) | 69 | 10 | SQS or bin; raises if neither; `enqueue_replace_assignment` |
| [`relocation_jobs/async_jobs/types.py`](../../relocation_jobs/async_jobs/types.py) | 20 | 10 | `ReplaceAssignment` message |

### Tests (characterization + seed)

| File | + | − | What |
|------|--:|--:|------|
| [`tests/helpers/seed.py`](../../tests/helpers/seed.py) | 146 | 0 | Test-only SQL: `replace_user_opportunities`, `ensure_company_assignments`, `seed_free_assignments` |
| [`tests/fetch/test_pipeline.py`](../../tests/fetch/test_pipeline.py) | 27 | 0 | Fetch scrape path does not enqueue; scheduler blocking is not a thread |
| [`tests/fetch/test_scheduler.py`](../../tests/fetch/test_scheduler.py) | 16 | 32 | Listing check is a sibling of the cycle |
| [`tests/test_entitlements.py`](../../tests/test_entitlements.py) | 26 | 5 | Board GET does not enqueue or write prefs |
| [`tests/web/test_personalized_board.py`](../../tests/web/test_personalized_board.py) | 15 | 6 | Board GET does not insert assignment rows |
| [`tests/test_broadcast_capacity.py`](../../tests/test_broadcast_capacity.py) | 38 | 7 | Consume without a row does not insert |
| [`tests/test_opportunities.py`](../../tests/test_opportunities.py) | 28 | 17 | Enqueue without writer raises; production repos have no create helpers |
| [`tests/test_google_auth.py`](../../tests/test_google_auth.py) | 27 | 0 | Login still writes prefs + enqueue (stubbed) |
| Other web/payment/conftest stubs | ~13 | ~11 | Enqueue stubs on write paths that used to be silent |

### Ops / docs / CI (in the same commit)

| File | + | − | What |
|------|--:|--:|------|
| [`scripts/ec2_app_deploy.sh`](../../scripts/ec2_app_deploy.sh) | 80 | 4 | Build/run `relocation-role-propagator`; pass SQS env to panel + worker |
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | 7 | 0 | `go test ./apps/role-propagator` |
| [`.env.example`](../../.env.example) | 7 | 2 | Enqueue requires SQS URL or `ROLE_PROPAGATOR_BIN` |
| [`.gitignore`](../../.gitignore) | 1 | 0 | Ignore built `apps/role-propagator/role-propagator` |
| [`docs/reference/architecture.md`](architecture.md) | 65 | 14 | Call graph after the move |
| Other docs (`entitlements`, `sqs-opportunity-refresh`, `ec2-panel`, `rules`, README) | ~22 | ~11 | Worker is Go; board GET is not a producer |

---

## What each phase did

Work followed the original plan’s phase order (characterization first, then fetch, reads, Go-only create, loud enqueue, leftover deletes, docs).

1. **Protect** — Tests that fail if board GET writes or enqueues, if fetch scrape imports enqueue, or if consume invents a row.
2. **Fetch soul** — One `main` in `scheduler.py`. Listing check is a sibling of the country cycle. Company fetch is top-down. Country semaphore is the only concurrency knob. Scheduler does not use `start_country_fetch` + join.
3. **Reads are reads** — Scope/flatten/peek only on GET. Bootstrap on login / prefs PUT / payment.
4. **Go is the only creator** — Python consume is `consumed_at` only. Create SQL lives in the test helper.
5. **Async transports intent** — Missing writer is an error on explicit write paths (board GET no longer enqueues, so the old silent no-op there is gone).
6. **Dead code** — Python consumer, ports, opportunity-worker, `refresh_opportunities` / `ensure_fresh`.
7. **Docs + verify** — Architecture matches this graph. Pytest `not scrape`: **559 passed**. `go test` in `apps/role-propagator`: **ok**.

---

## Final result (Definition of Done)

Answerable from the call graph, not tribal knowledge:

| Question | Answer |
|----------|--------|
| Where does country fetch start? | `apps/fetch-worker` → `scheduler` → `run_country_fetch` |
| Where is concurrency? | Country `asyncio.Semaphore` only |
| Where does persist happen? | `pipeline` / `service` → `sync_company_board_to_catalog` |
| Does board GET write slots or enqueue? | No |
| Who creates assignments? | Go `apps/role-propagator` |
| What may Python write on a user action? | `consumed_at` (and `engaged`) on an existing row |
| Who owns limits? | `users/entitlements.py` (Go reads the same env vars) |
| What is on the queue? | `{type:user\|country\|replace}` |
| Who consumes the queue? | Go. Failure = SQS visibility + DLQ (`maxReceiveCount=3`) |

**Production after deploy (2026-09-09):** panel `/api/health` 200 on kuchup.com; fetch scheduler running; role-propagator container running.

**Known leftover:** the propagator logged `job failed type=user user=N: no rows in result set` for IDs that are no longer in `users`. Prefs-missing is already handled (`ErrNoRows` → default country). Those messages retry then DLQ. Drain or ignore the DLQ; it is not board GET inventing work anymore.

---

## How to run

```bash
# Panel (local)
PANEL_SCRAPE_ENABLED=1 python3 apps/panel/run.py

# Fetch once
FETCH_SCHEDULE_ENABLED=1 python3 apps/fetch-worker/run.py --once

# Assignment writer (local, no SQS)
ROLE_PROPAGATOR_BIN=./apps/role-propagator/role-propagator
# or
go run ./apps/role-propagator --once

# Tests
.venv/bin/pytest tests -m 'not scrape' -o addopts=
go test ./apps/role-propagator
```

Local login / prefs PUT / payment **raise** if neither `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` nor `ROLE_PROPAGATOR_BIN` is set. That is intentional.
