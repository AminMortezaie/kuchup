# Production monitoring (Grafana Cloud Free)

**Stack:** tiny **ops-agent** on EC2 (default) → Grafana Cloud Prometheus + Postgres `ops_metric_samples` → dashboards + email alerts + synthetics  
**Legacy:** Grafana Alloy (`relocation-alloy`) — escape hatch via `MONITORING_AGENT=alloy` for a short baseline window  
**App probe:** `GET https://kuchup.com/api/health`  
**Ops CLI:** `./scripts/ec2_app_deploy.sh status` · `logs` (SSH live-tail)

Grafana Cloud Free keeps metrics ~14 days. This repo also **persists the same gauge samples in Postgres** (`ops_metric_samples`) for before/after comparisons (memory tuning, Alloy → ops-agent cutover, etc.).

Do not commit API tokens — gitignored `.env` only.

---

## Architecture

| Piece | Role |
|-------|------|
| `GET /api/health` | Unauthenticated; probes Postgres + Redis; **200** / **503** |
| **ops-agent** (`relocation-ops-agent`, default) | Host `/proc` + root disk, Docker stats for named containers, blackbox probe of `http://host.docker.internal:10000/api/health`; **remote_write** to Grafana Cloud; **INSERT** into `ops_metric_samples` |
| Grafana Alloy (`relocation-alloy`, optional) | Same Prometheus metrics + optional Loki log ship when `MONITORING_AGENT=alloy` |
| Grafana Cloud Free | Metrics (Prometheus), logs (Loki when Alloy runs), dashboards, alert rules, email contact points |
| Cloud synthetics | Hit public `https://kuchup.com/api/health` (catches Cloudflare 522 when origin is dead) |

**Config:** committed template [`apps/ops-agent/env.example`](../../apps/ops-agent/env.example). Deploy sets env from `.env` / `aws-postgres.env` (no gitignored `deploy/ec2/` files required). Legacy Alloy still uses gitignored `deploy/ec2/config.alloy`.

ops-agent runs with `--pid=host`, `/proc` and `/` mounted read-only, and Docker socket read-only (same idea as Alloy/cAdvisor, without cAdvisor). Expected RSS **under ~10 MiB** with `--memory=32m` cap on the container.

**Logs (Loki):** not shipped by ops-agent (keeps memory small). Live tails: `./scripts/ec2_app_deploy.sh logs …`. Historical logs in Grafana Loki only while Alloy runs with Loki credentials (~14 days). After cutover, use SSH logs for live debugging and Loki only if you temporarily set `MONITORING_AGENT=alloy`.

App containers use the json-file log driver with `max-size=10m` / `max-file=3` so Docker logs cannot fill the root volume.

---

## Deploy / cutover

Default (ops-agent replaces Alloy on deploy):

```bash
./scripts/ec2_app_deploy.sh deploy
```

| Variable | Meaning |
|----------|---------|
| `MONITORING_AGENT=ops` | **Default.** Build/run `relocation-ops-agent`, remove Alloy |
| `MONITORING_AGENT=alloy` | Run legacy Alloy (metrics ± Loki); remove ops-agent — use briefly to dual-compare in Grafana, not in Postgres |

**Cutover notes:** ops-agent **dual-writes** from the first deploy (Grafana remote_write when `GRAFANA_CLOUD_*` is set, always Postgres when `DATABASE_URL` is set). There is no separate bridge job: run `MONITORING_AGENT=alloy` for one interval if you need overlapping Grafana series, then redeploy with `ops` (default). Postgres history starts as soon as ops-agent runs and the `ops_metric_samples_v1` migration has applied (panel/worker startup).

Prometheus credentials missing → ops-agent still runs and writes Postgres; remote_write is skipped (same as former “Alloy skipped” for metrics-only gap).

---

## Postgres: `ops_metric_samples`

Applied by startup migration `ops_metric_samples_v1`:

| Column | Type |
|--------|------|
| `recorded_at` | `timestamptz` |
| `metric` | `text` |
| `labels` | `jsonb` |
| `value` | `double precision` |

Index: `(metric, recorded_at DESC)`.

**Example queries** (psql or Admin SQL):

```sql
-- Panel health last 7 days (5m buckets)
SELECT date_trunc('minute', recorded_at) AS t,
       avg(value) AS probe_ok
FROM ops_metric_samples
WHERE metric = 'probe_success'
  AND labels->>'job' = 'integrations/blackbox'
  AND recorded_at > now() - interval '7 days'
GROUP BY 1 ORDER BY 1;

-- MemAvailable before/after a deploy
SELECT recorded_at, value / 1024 / 1024 AS mem_avail_mib
FROM ops_metric_samples
WHERE metric = 'node_memory_MemAvailable_bytes'
  AND recorded_at BETWEEN '2026-03-01' AND '2026-03-02'
ORDER BY recorded_at;

-- Container memory snapshot (matches Grafana panel filter)
SELECT recorded_at, labels->>'name' AS container, value / 1024 / 1024 AS mib
FROM ops_metric_samples
WHERE metric = 'container_memory_usage_bytes'
  AND labels->>'name' ~ '^(relocation-.*|pg)$'
ORDER BY recorded_at DESC
LIMIT 50;
```

Python insert helper (optional bridges/tests): `relocation_jobs.ops.repo.insert_ops_metric_samples`.

---

## One-time Grafana Cloud setup

1. Create a free stack at [grafana.com](https://grafana.com/auth/sign-up/create-user).
2. Access policy with **metrics:write** (and **logs:write** only if you still run Alloy + Loki).
3. Prometheus → **Send metrics** → remote_write URL + user → `.env`:

```bash
GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-XX-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROMETHEUS_USER=123456
GRAFANA_CLOUD_API_TOKEN=glc_...
```

4. Optional Loki (Alloy only):

```bash
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-XX-XX.grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USER=123456
```

5. Deploy; confirm Explore (Prometheus): `node_filesystem_avail_bytes`, `container_memory_usage_bytes`, `probe_success`.

---

## Dashboards (import)

Import a dashboard with those panels (JSON lives in gitignored `deploy/ec2/`, not the public tree):

1. Grafana → **Dashboards** → **New** → **Import**
2. Use local `deploy/ec2/grafana-dashboard-kuchup.json` if you have it, or recreate from PromQL below
3. Pick your Grafana Cloud **Prometheus** datasource

| Panel | PromQL |
|-------|--------|
| Disk used % | `100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})` |
| Memory available | `node_memory_MemAvailable_bytes` |
| Container memory | `container_memory_usage_bytes{name=~"relocation-.*\|pg"}` |
| Panel health | `probe_success{job="integrations/blackbox"}` |
| Load / CPU | `node_load1`, `rate(container_cpu_usage_seconds_total[5m])` |

Alert rule recipes (email) — create in Grafana Cloud:

---

## Logs (Loki, Alloy only)

When `MONITORING_AGENT=alloy` and Loki env vars are set, search Explore → **Loki**:

| Query | What |
|-------|------|
| `{name="relocation-panel"}` | Gunicorn access / error |
| `{name="relocation-fetch-worker"}` | Scheduled country scrape |
| `{name="relocation-caddy"}` | TLS / reverse proxy |
| `{name="relocation-mcp"}` | Remote MCP |

**Live tail** (always):

```bash
./scripts/ec2_app_deploy.sh logs panel 100
./scripts/ec2_app_deploy.sh logs worker 50 -f
```

---

## Synthetics (outside the box)

Grafana Cloud → **Synthetic Monitoring**:

- URL: `https://kuchup.com/api/health`
- Expect **200**
- Interval: **1–5 minutes**

---

## Email alerts

| Rule | Condition |
|------|-----------|
| Disk high | filesystem used > **80%** for 10m (critical > **90%**) |
| Memory low | `MemAvailable` < ~200MiB for 10m |
| Health probe | `probe_success == 0` for 5m |
| Synthetic | check failed |

---

## Ops commands

```bash
./scripts/ec2_app_deploy.sh status
./scripts/ec2_app_deploy.sh logs ops-agent 50
./scripts/ec2_app_deploy.sh logs panel 100
```

---

## Related

- [ec2-panel.md](ec2-panel.md) — deploy, Caddy, stack
- [aws-postgres.md](aws-postgres.md) — Postgres on EC2
