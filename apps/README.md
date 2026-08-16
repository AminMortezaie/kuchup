# Apps (deployables)

Thin, discoverable entrypoints for the product’s runnable services. Domain logic stays in [`relocation_jobs/`](../relocation_jobs/). Docker and existing ops scripts still call [`scripts/`](../scripts/); these folders exist so “where do I run X?” is obvious.

| App | Run locally | What it is |
|-----|-------------|------------|
| **panel** | `python3 apps/panel/run.py` | Flask job board + API (`:5051`) |
| **fetch-worker** | `python3 apps/fetch-worker/run.py` | Scheduled country scrape worker |
| **opportunity-worker** | `python3 apps/opportunity-worker/run.py` | SQS async_jobs reconcile worker |
| **mcp** (stdio) | `python3 apps/mcp/run.py` | Claude Desktop MCP (stdio) |
| **mcp** (HTTP) | `python3 apps/mcp/run_http.py` | Streamable HTTP MCP + OAuth |

Equivalent scripts (used by Docker / deploy): `scripts/panel_server.py`, `scripts/fetch_scheduler_worker.py`, `scripts/opportunity_sqs_worker.py`, `scripts/mcp_server.py`, `scripts/mcp_http_server.py`.

## Domains vs apps

```
apps/                  ← how you run it (deployables)
relocation_jobs/       ← domain code (catalog, panel, fetch, scrape, …)
frontend/              ← React board widget → static/dist/
homepage/              ← marketing site (Next.js; same-origin /api/public/*)
scripts/               ← ops + legacy entry paths for Docker
docs/                  ← documentation
```

Stay in one repo: panel, workers, and MCP share Postgres, `core/`, and migrations. See [architecture.md](../docs/reference/architecture.md).
