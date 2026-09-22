# Documentation

**Last updated:** 2026-09-16

All project docs live under `docs/`. [README](../README.md) at the repo root covers product setup and usage. Repo map (apps vs domains): [apps/README.md](../apps/README.md).

Code is the source of truth. This index lists **living** pages first. History sits in [archive/](archive/README.md). Unshipped designs sit in [proposals/](proposals/README.md).

---

## Quick paths

| I want to… | Read |
|------------|------|
| Install and run the panel | [README](../README.md) |
| Find apps vs domains | [apps/README.md](../apps/README.md) |
| Set up for development | [contributing.md](contributing.md) |
| Understand code layout & data flow | [reference/architecture.md](reference/architecture.md) |
| Change Python in `relocation_jobs/` | [reference/rules.md](reference/rules.md) |
| Change job apply / reject / hide behavior | [reference/business-rules.md](reference/business-rules.md) |
| Work on board sort, pagination, newest | [reference/board.md](reference/board.md) |
| Panel UI health check (React island + vanilla hybrid) | [reference/frontend-health-check.md](reference/frontend-health-check.md) |
| Entitlements — Google auth, plans, credits, NOWPayments | [reference/entitlements-and-opportunities.md](reference/entitlements-and-opportunities.md) |
| Catalog vs per-user tracking | [reference/catalog-pattern.md](reference/catalog-pattern.md) |
| Panel / admin statistics | [reference/stats.md](reference/stats.md) |
| Secrets / no real IPs in public docs | [reference/rules.md](reference/rules.md#secrets-and-documentation) · `.env` / `aws-postgres.env` gitignored |
| MCP apply assistant | [reference/mcp-application.md](reference/mcp-application.md) |
| Company workspace (CV/PDF on panel) | [reference/company-workspace.md](reference/company-workspace.md) |
| Public job pages / LinkedIn wrapping | [reference/job-syndication.md](reference/job-syndication.md) |
| SEO indexing | [operations/seo-indexing.md](operations/seo-indexing.md) |
| **Production panel (EC2, kuchup.com)** | [operations/ec2-panel.md](operations/ec2-panel.md) |
| **AWS Postgres on that host** | [operations/aws-postgres.md](operations/aws-postgres.md) |
| **NOWPayments checkout** | [operations/nowpayments.md](operations/nowpayments.md) |
| **Production monitoring (Grafana Cloud)** | [operations/monitoring.md](operations/monitoring.md) |
| Domain email (`@kuchup.com`) | [operations/email.md](operations/email.md) |
| **SQS opportunity refresh queue** | [operations/sqs-opportunity-refresh.md](operations/sqs-opportunity-refresh.md) |
| Planned work | [backlog.md](backlog.md) · [proposals/](proposals/README.md) |
| Postmortems / shipped write-ups | [archive/](archive/README.md) |

---

## Layout

```
docs/
  README.md                 ← this index
  contributing.md           dev setup, tests, where to code
  backlog.md                planned work
  reference/                living architecture and product contracts
  operations/               live production runbooks
  proposals/                unshipped designs
  archive/                  postmortems and shipped history
```

---

## By topic

### Development

| Doc | Purpose |
|-----|---------|
| [contributing.md](contributing.md) | First 15 minutes, domains, tests, database, fetch |
| [reference/architecture.md](reference/architecture.md) | Data flow, package layout, panel read path, fetch worker |
| [reference/rules.md](reference/rules.md) | Layer boundaries, naming, scrape/fetch, tests |
| [reference/schemas.md](reference/schemas.md) | Pydantic models and catalog envelope |
| [.cursor/rules/v2-coding.mdc](../.cursor/rules/v2-coding.mdc) | Cursor summary of rules |

### Panel behavior

| Doc | Purpose |
|-----|---------|
| [reference/board.md](reference/board.md) | Board API, pagination, newest sort |
| [reference/frontend-health-check.md](reference/frontend-health-check.md) | Panel UI health check — React island, vanilla JS, what to do next |
| [reference/stats.md](reference/stats.md) | Admin/user stats definitions |
| [reference/business-rules.md](reference/business-rules.md) | Job state contracts — read before tracking changes |

### Data

| Doc | Purpose |
|-----|---------|
| [reference/catalog-pattern.md](reference/catalog-pattern.md) | Shared catalog vs per-user overlay |
| [reference/job-syndication.md](reference/job-syndication.md) | Public `/jobs/<slug>` pages, JSON-LD, LinkedIn capture funnel |
| [reference/entitlements-and-opportunities.md](reference/entitlements-and-opportunities.md) | Plans, credits, sticky slots, Go assignment writer |

### MCP / apply

| Doc | Purpose |
|-----|---------|
| [reference/mcp-application.md](reference/mcp-application.md) | MCP tools, `/apply`, resume tex → PDF |
| [reference/company-workspace.md](reference/company-workspace.md) | `/company/<country>/<slug>` — CV, cover letter, JD fetch |

### Operations

| Doc | Purpose |
|-----|---------|
| [operations/aws-postgres.md](operations/aws-postgres.md) | EC2 Docker Postgres, `sync-sg`, backups |
| [operations/ec2-panel.md](operations/ec2-panel.md) | EC2 deploy, kuchup.com, Caddy, Cloudflare |
| [operations/monitoring.md](operations/monitoring.md) | Grafana Cloud Free, Alloy, `/api/health`, alerts |
| [operations/email.md](operations/email.md) | `@kuchup.com` via Cloudflare Email Routing |
| [operations/nowpayments.md](operations/nowpayments.md) | Credit packs + Full Access checkout |
| [operations/seo-indexing.md](operations/seo-indexing.md) | Search Console, `/sitemap.xml` + `/sitemap-jobs.xml` |
| [operations/sqs-opportunity-refresh.md](operations/sqs-opportunity-refresh.md) | Opportunity assignment queue (Go consumer) |
| `scripts/ec2_app_deploy.sh` | Panel deploy to EC2 |
| `scripts/ec2_redis.sh` | Redis on EC2 |

Caddyfile and Grafana Alloy config live in **gitignored** `deploy/ec2/` (not in the public tree). The deploy script copies them onto the host.

### Proposals (not on `main` yet)

| Doc | Purpose |
|-----|---------|
| [proposals/README.md](proposals/README.md) | Status of open designs |
| [board-read-model-proposal.md](proposals/board-read-model-proposal.md) | Board projection / cursor pagination |
| [multi-user-scaling-proposal.md](proposals/multi-user-scaling-proposal.md) | SQS for fetch/PDF; Phase 0 pool already shipped |
| [kafka-fetch-pipeline-proposal.md](proposals/kafka-fetch-pipeline-proposal.md) | Fetch work queue (not the opportunity SQS) |
| [full-spa-ui-modernization-proposal.md](proposals/full-spa-ui-modernization-proposal.md) | Full React SPA |

### Archive

| Doc | Purpose |
|-----|---------|
| [archive/README.md](archive/README.md) | Postmortems, v1 parity, Neon migration, shipped refactors |

---

## Root entry points

| File | Role |
|------|------|
| [README.md](../README.md) | Product + quick start |
| [AGENTS.md](../AGENTS.md) | Agent pointer → this index |
| [apps/README.md](../apps/README.md) | How to run panel / workers / MCP |
| [design.md](../design.md) | Locked UI design system |

`CLAUDE.md` and `.claude/skills/` are gitignored local notes, not part of the public docs set.

**Do not commit** unless explicitly asked.
