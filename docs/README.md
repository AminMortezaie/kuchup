# Documentation

**Last updated:** 2026-09-06

All project docs live under `docs/`. [README](../README.md) at the repo root covers product setup and usage only. Repo map (apps vs domains): [apps/README.md](../apps/README.md).

---

## Quick paths

| I want to… | Read |
|------------|------|
| Install and run the panel | [README](../README.md) |
| Find apps vs domains (repo map) | [apps/README.md](../apps/README.md) · [architecture.md](reference/architecture.md#repo-map) |
| Set up for development | [contributing.md](contributing.md) |
| Understand code layout & data flow | [reference/architecture.md](reference/architecture.md) |
| Change Python in `relocation_jobs/` | [reference/rules.md](reference/rules.md) |
| Change job apply / reject / hide behavior | [reference/business-rules.md](reference/business-rules.md) |
| Work on board sort, pagination, newest | [reference/board.md](reference/board.md) |
| Board performance / read-model design (proposal) | [reference/board-read-model-proposal.md](reference/board-read-model-proposal.md) |
| Fetch pipeline queue / Kafka placement (proposal) | [reference/kafka-fetch-pipeline-proposal.md](reference/kafka-fetch-pipeline-proposal.md) |
| Multi-user scaling — SQS broker, DB pool, board projection (proposal) | [reference/multi-user-scaling-proposal.md](reference/multi-user-scaling-proposal.md) |
| Entitlements — Google auth, plans, credits, NOWPayments checkout | [reference/entitlements-and-opportunities.md](reference/entitlements-and-opportunities.md) |
| Full SPA UI modernization (proposal) | [reference/full-spa-ui-modernization-proposal.md](reference/full-spa-ui-modernization-proposal.md) |
| Single-company fetch modal session (why it felt flaky) | [reference/fetch-panel-session.md](reference/fetch-panel-session.md) |
| Catalog vs per-user tracking (design) | [reference/catalog-pattern.md](reference/catalog-pattern.md) |
| Panel / admin statistics | [reference/stats.md](reference/stats.md) |
| Test failures / catalog seed in tests | [reference/catalog-seed-test-failure.md](reference/catalog-seed-test-failure.md) |
| Board hung / slow load (2026-07 postmortem) | [reference/board-load-performance-incident.md](reference/board-load-performance-incident.md) |
| Country cache Redis hot-path regression (2026-07 postmortem) | [reference/country-cache-redis-hotpath-incident.md](reference/country-cache-redis-hotpath-incident.md) |
| Fetch scheduler hung / timeouts (2026-07) | [reference/fetch-scheduler-timeout-practices.md](reference/fetch-scheduler-timeout-practices.md) |
| Fetch thread exhaustion / `can't start new thread` (2026-09 postmortem) | [reference/fetch-thread-exhaustion-incident.md](reference/fetch-thread-exhaustion-incident.md) |
| Fetch concurrency model review (2026-09) | [reference/fetch-concurrency-model-review.md](reference/fetch-concurrency-model-review.md) |
| Secrets / no real IPs in public docs | [reference/rules.md](reference/rules.md#secrets-and-documentation) · `.env` / `aws-postgres.env` gitignored |
| MCP apply assistant (Claude Desktop, v0) | [reference/mcp-application.md](reference/mcp-application.md) |
| Company workspace (CV/PDF on panel) | [reference/company-workspace.md](reference/company-workspace.md) |
| Public job pages / LinkedIn wrapping | [reference/job-syndication.md](reference/job-syndication.md) |
| SEO indexing (Search Console, sitemaps) | [operations/seo-indexing.md](operations/seo-indexing.md) |
| **Production panel (EC2, kuchup.com)** | [operations/ec2-panel.md](operations/ec2-panel.md) |
| **NOWPayments checkout (credits + Full Access)** | [operations/nowpayments.md](operations/nowpayments.md) |
| **Production monitoring (Grafana Cloud)** | [operations/monitoring.md](operations/monitoring.md) |
| Domain email (`@kuchup.com`) | [operations/email.md](operations/email.md) |
| **SQS opportunity refresh queue** | [operations/sqs-opportunity-refresh.md](operations/sqs-opportunity-refresh.md) |
| Agent commands cheat sheet | [CLAUDE.md](../CLAUDE.md) |

---

## Layout

```
docs/
  README.md                 ← this index
  contributing.md           dev setup, tests, where to code
  backlog.md                  planned work
  reference/
    architecture.md           data flow, package layout, panel read path
    board.md                  pagination, “newest first” sort, timestamps
    board-read-model-proposal.md  board performance: projection table, cursors (proposal)
    kafka-fetch-pipeline-proposal.md  fetch/scrape work queue, Kafka placement (proposal)
    multi-user-scaling-proposal.md  SQS job queue, DB pool, board projection for many users (proposal)
    full-spa-ui-modernization-proposal.md  React SPA, design system, dark/light, mobile (proposal)
    fetch-panel-session.md    single-company fetch modal: session ownership + settle-once UX
    stats.md                  admin/user stats definitions
    business-rules.md         job buckets, orphans, apply/reject/not-for-me
    rules.md                  v2 coding standards (SQL in repo.py)
    schemas.md                Pydantic models, catalog shape
    parity.md                 v1 vs v2 checklist (complete)
    catalog-pattern.md        shared catalog + per-user overlay (design)
    catalog-seed-test-failure.md  post-mortem: pytest pollution after board sort tests
    country-cache-redis-hotpath-incident.md  post-mortem: Redis I/O in country-label hot path
    fetch-thread-exhaustion-incident.md      post-mortem: can't start new thread (2026-09)
    fetch-concurrency-model-review.md        review: one event loop + semaphore (2026-09)
    mcp-application.md          Claude Desktop MCP: resume tex → PDF, apply prep (v0)
    company-workspace.md        Panel company page: tailored CV + PDF preview
    job-syndication.md          Public /jobs/<slug> pages, JobPosting JSON-LD, LinkedIn funnel
  operations/
    aws-postgres.md           AWS EC2 Postgres
    ec2-panel.md              Panel on EC2, kuchup.com, Caddy
    monitoring.md             Grafana Cloud Free + Alloy
    email.md                  Domain email via Cloudflare Email Routing
    nowpayments.md            NOWPayments credit packs + Full Access checkout
    seo-indexing.md           Search Console, marketing + jobs sitemaps
```

---

## By topic

### Development

| Doc | Purpose |
|-----|---------|
| [contributing.md](contributing.md) | First 15 minutes, domains, tests, database, fetch |
| [reference/architecture.md](reference/architecture.md) | Data flow, v2 layout, panel read path, client patterns |
| [reference/rules.md](reference/rules.md) | Layer boundaries, naming, scrape/fetch, tests |
| [.cursor/rules/v2-coding.mdc](../.cursor/rules/v2-coding.mdc) | Cursor summary of rules |

Agent skills: `.claude/skills/` (`getting-started` → `collaboration-style` → `engineering-standards` → …)

### Panel behavior

| Doc | Purpose |
|-----|---------|
| [reference/board.md](reference/board.md) | Board API, pagination, newest sort (mermaid) |
| [reference/fetch-panel-session.md](reference/fetch-panel-session.md) | Single-company fetch modal session (stale UI / double board update) |
| [reference/stats.md](reference/stats.md) | Admin/user stats definitions |
| [reference/business-rules.md](reference/business-rules.md) | Job state contracts — read before tracking changes |

### Data

| Doc | Purpose |
|-----|---------|
| [reference/schemas.md](reference/schemas.md) | Pydantic models and catalog envelope |
| [reference/catalog-pattern.md](reference/catalog-pattern.md) | Shared catalog vs per-user overlay |
| [reference/job-syndication.md](reference/job-syndication.md) | Public `/jobs/<slug>` pages, JSON-LD, LinkedIn capture funnel |
| [reference/parity.md](reference/parity.md) | v1 removal / cutover status |

### Operations

| Doc | Purpose |
|-----|---------|
| [operations/aws-postgres.md](operations/aws-postgres.md) | AWS Postgres migration and day-to-day ops |
| [operations/ec2-panel.md](operations/ec2-panel.md) | EC2 deploy, kuchup.com, Caddy, Cloudflare lock-down |
| [operations/monitoring.md](operations/monitoring.md) | Grafana Cloud Free, Alloy, `/api/health`, alerts |
| [operations/email.md](operations/email.md) | `@kuchup.com` via Cloudflare Email Routing + Gmail Send as |
| [operations/seo-indexing.md](operations/seo-indexing.md) | Search Console, `/sitemap.xml` + `/sitemap-jobs.xml`, `/engineering` notes |
| `scripts/ec2_app_deploy.sh` | Panel deploy to EC2 |
| `scripts/ec2_redis.sh` | Redis on EC2 |

### Backlog

| Doc | Purpose |
|-----|---------|
| [backlog.md](backlog.md) | Living backlog |

---

## Root entry points (tools)

| File | Role |
|------|------|
| [README.md](../README.md) | Product + quick start |
| [AGENTS.md](../AGENTS.md) | Agent pointer → this index |
| [CLAUDE.md](../CLAUDE.md) | Commands + current focus |

**Do not commit** unless explicitly asked.
