# Production monitoring (Grafana Cloud Free)

**Stack:** Grafana Alloy on EC2 → Grafana Cloud Prometheus + Loki → dashboards + log search + email alerts + synthetics  
**App probe:** `GET https://kuchup.com/api/health`  
**Ops CLI:** `./scripts/ec2_app_deploy.sh status` · `logs` (SSH live-tail)

This is the production-shaped, interview-relevant path (Prometheus metrics + Loki logs + Grafana). Stay on **Grafana Cloud Free** ($0 within free limits: 50 GB logs/month, 14-day retention). Do not commit API tokens — gitignored `.env` only.

---

## Architecture

| Piece | Role |
|-------|------|
| `GET /api/health` | Unauthenticated; probes Postgres + Redis; **200** / **503** |
| Grafana Alloy (`relocation-alloy`) | Host (node), Docker (cAdvisor), blackbox probe of local `/api/health`; Docker logs from panel / worker / MCP / Caddy |
| Grafana Cloud Free | Metrics (Prometheus), logs (Loki), dashboards, alert rules, email contact points |
| Cloud synthetics | Hit public `https://kuchup.com/api/health` (catches Cloudflare 522 when origin is dead) |

Config in repo: [`deploy/ec2/config.alloy`](../../deploy/ec2/config.alloy). Secrets via env from local `.env` at deploy time.

Alloy runs **privileged** with `/sys` and `/var/lib/docker` mounted so cAdvisor can attach the Docker `name` label. Without that, host/`probe_success` panels work but container memory/CPU stay **No data**. Docker socket is the same mount Loki uses to tail container stdout.

App containers use the json-file log driver with `max-size=10m` / `max-file=3` so Docker logs cannot fill the root volume. Recreate (deploy) applies rotation to panel / MCP / worker / Caddy / Alloy. Postgres and Redis pick it up only on the next `docker run` (do not recreate `pg` just for this).

---

## One-time Grafana Cloud setup

1. Create a free stack at [grafana.com](https://grafana.com/auth/sign-up/create-user) (Free forever; no credit card required for Free).
2. Create an **access policy** with **metrics:write** and **logs:write** (or add `logs:write` to the existing policy). Copy the token → `GRAFANA_CLOUD_API_TOKEN`.
3. Open your stack → **Connections** / **Prometheus** → **Send metrics** → copy **remote_write** details:
   - URL → `GRAFANA_CLOUD_PROMETHEUS_URL` (ends with `/api/prom/push`)
   - Username (instance id) → `GRAFANA_CLOUD_PROMETHEUS_USER`
4. Same stack → **Loki** → **Send logs** → copy push details (Loki user is a different instance id than Prometheus):
   - URL → `GRAFANA_CLOUD_LOKI_URL` (ends with `/loki/api/v1/push`)
   - Username → `GRAFANA_CLOUD_LOKI_USER`
5. Add to **gitignored** `.env` (see [`.env.example`](../../.env.example)):

```bash
GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-XX-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROMETHEUS_USER=123456
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-XX-XX.grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USER=123456
GRAFANA_CLOUD_API_TOKEN=glc_...
```

6. Deploy so Alloy starts (Prometheus credentials required or Alloy is skipped; Loki vars optional — without them Alloy ships metrics only):

```bash
./scripts/ec2_app_deploy.sh deploy
# or after sync only — full deploy recreates Alloy:
./scripts/ec2_app_deploy.sh sync
# then recreate Alloy by re-running deploy, or SSH and start manually
```

7. In Grafana Explore (Prometheus), confirm series such as `node_filesystem_avail_bytes`, `container_memory_usage_bytes`, `probe_success`.
8. In Grafana Explore (Loki), confirm `{name="relocation-panel"}` returns gunicorn lines.

If Prometheus credentials are missing, deploy logs `Alloy skipped` and removes any old `relocation-alloy` container.

---

## Logs (Loki)

Search in Grafana → **Explore** → datasource **Loki**. Container recreate on deploy wipes local `docker logs`; Loki keeps ~14 days.

| Query | What |
|-------|------|
| `{name="relocation-panel"}` | Gunicorn access / error |
| `{name="relocation-fetch-worker"}` | Scheduled country scrape |
| `{name="relocation-caddy"}` | TLS / reverse proxy |
| `{name="relocation-mcp"}` | Remote MCP |
| `{name="relocation-panel"} \|= "ERROR"` | Panel errors |
| `{name="relocation-fetch-worker"} \|= "ERROR"` | Fetch failures |
| `{job="docker"} \|= "credit_"` | Credit checkout / grant lines |

App processes emit **JSON lines on stderr** (`LOG_FORMAT=json` in Docker / when stderr is not a TTY; `console` on a local TTY). Set `LOG_LEVEL` (default `INFO`). Explore `{name="relocation-panel"}` and `{name="relocation-fetch-worker"}` — fetch events carry fields such as `run_id` and `country`. The fetch modal still polls a capped `log_json` buffer (last 200 lines); Loki is the archive. Gunicorn access stays CLF on stdout.

Worker HTTP body previews can be chatty during a country cycle. If Free ingest looks high, lower `FETCH_LOG_BODY_LIMIT` — do not ship Postgres or Redis logs.

**Live tail** (this moment, this box) is still SSH:

```bash
./scripts/ec2_app_deploy.sh logs panel 100
./scripts/ec2_app_deploy.sh logs worker 50 -f
```

Use Loki for “what happened two hours ago / after the last deploy.” Use `logs` for “is this scrape hung right now.”

---

## Dashboards (import)

Import the ready dashboard (disk, memory, containers, health probe):

1. Grafana → **Dashboards** → **New** → **Import**
2. Upload [`deploy/ec2/grafana-dashboard-kuchup.json`](../../deploy/ec2/grafana-dashboard-kuchup.json)
3. Pick your Grafana Cloud **Prometheus** datasource when prompted
4. Open **kuchup EC2 health** (`uid: kuchup-ec2-health`)

| Panel | PromQL |
|-------|--------|
| Disk used % | `100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})` |
| Memory available | `node_memory_MemAvailable_bytes` |
| Container memory | `container_memory_usage_bytes{name=~"relocation-.*\|pg"}` |
| Panel health | `probe_success{job="integrations/blackbox"}` |
| Load / CPU | `node_load1`, `rate(container_cpu_usage_seconds_total[...][5m])` |

Alert rule recipes (email): [`deploy/ec2/grafana-alert-rules.md`](../../deploy/ec2/grafana-alert-rules.md).

---

## Synthetics (outside the box)

In Grafana Cloud → **Synthetic Monitoring** (or **Alerting** HTTP check):

- URL: `https://kuchup.com/api/health`
- Expect status **200**
- Interval: **1–5 minutes**
- Alert when failing

This is what catches origin hangs when SSH and Alloy on the box are also dead.

---

## Email alerts

1. **Alerting** → **Contact points** → add **Email** (your address).
2. Add notification policy routing critical alerts to that contact.
3. Create rules from [`deploy/ec2/grafana-alert-rules.md`](../../deploy/ec2/grafana-alert-rules.md):

| Rule | Condition |
|------|-----------|
| Disk high | filesystem used > **80%** for 10m (critical > **90%**) |
| Memory low | `MemAvailable` < ~200MiB for 10m |
| Health probe | `probe_success == 0` for 5m |
| Synthetic | check failed |

Send a test notification once.

---

## Ops commands

Grafana Explore → Loki for history (`{name="relocation-panel"}`). SSH live-tail:

```bash
./scripts/ec2_app_deploy.sh status          # disk, RAM, containers, /api/health, layer verdict
./scripts/ec2_app_deploy.sh logs panel 100
./scripts/ec2_app_deploy.sh logs caddy
./scripts/ec2_app_deploy.sh logs worker 50 -f
./scripts/ec2_app_deploy.sh logs all 30
```

Layer verdicts from `status`: `all_ok`, `origin_ok_cf_fail`, `panel_down`, `degraded`.

## Credit wallet checks

- Admin audit: `GET /api/admin/credits/audit` reports invalid grant balances,
  ledger/balance mismatches, and paid orders without a corresponding grant.
- Panel logs emit `credit_checkout_started`, `credit_payment_event`, and
  `credit_admin_grant` for conversion and incident investigation.
- Alert on any non-empty `paid_orders_without_grants` result. Reconcile a paid
  order with `POST /api/admin/credit-orders/<order_id>/reconcile`; the grant is
  idempotent.

---

## Incident: Cloudflare 522 / host hung

**Meaning:** Cloudflare could not get a timely response from origin (not an app 5xx).

| Observation (`status`) | Likely layer |
|------------------------|--------------|
| Panel localhost **200**, domain fail | Cloudflare ↔ Caddy / SG / Caddy |
| Panel localhost fail, containers Exited | Panel/Caddy crash or OOM |
| Containers Up, localhost hang / SSH banner timeout | Host wedged (disk/memory) |
| Domain + EIP both timeout | SG / instance / network |

**Known causes on this host (2026):** root disk filling with Docker layers (`no space left on device`); memory cliff (fetch-worker ~560MiB idle, no swap, Playwright concurrency). Soft reboot may not recover; **stop/start** did.

**Runbook:** Grafana disk/RAM panels → Explore Loki `{name="relocation-caddy"}` / `{name="relocation-panel"}` → `./scripts/ec2_app_deploy.sh status` → `logs caddy` / `logs panel` for live tail → do **not** terminate the instance (EBS `DeleteOnTermination`); prefer stop/start. Postgres lives in Docker volume `pgdata`.

---

## Related

- [ec2-panel.md](ec2-panel.md) — deploy, Caddy, stack
- [aws-postgres.md](aws-postgres.md) — Postgres on EC2
