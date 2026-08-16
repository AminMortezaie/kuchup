# Production monitoring (Grafana Cloud Free)

**Stack:** Grafana Alloy on EC2 → Grafana Cloud Prometheus → dashboards + email alerts + synthetics  
**App probe:** `GET https://kuchup.com/api/health`  
**Ops CLI:** `./scripts/ec2_app_deploy.sh status` · `logs`

This is the production-shaped, interview-relevant path (Prometheus metrics + Grafana). Stay on **Grafana Cloud Free** ($0 within free limits). Do not commit API tokens — gitignored `.env` only.

---

## Architecture

| Piece | Role |
|-------|------|
| `GET /api/health` | Unauthenticated; probes Postgres + Redis; **200** / **503** |
| Grafana Alloy (`relocation-alloy`) | Host (node), Docker (cAdvisor), blackbox probe of local `/api/health`; `remote_write` to Cloud |
| Grafana Cloud Free | Store metrics, dashboards, alert rules, email contact points |
| Cloud synthetics | Hit public `https://kuchup.com/api/health` (catches Cloudflare 522 when origin is dead) |

Config in repo: [`deploy/ec2/config.alloy`](../../deploy/ec2/config.alloy). Secrets via env from local `.env` at deploy time.

Alloy runs **privileged** with `/sys` and `/var/lib/docker` mounted so cAdvisor can attach the Docker `name` label. Without that, host/`probe_success` panels work but container memory/CPU stay **No data**.

---

## One-time Grafana Cloud setup

1. Create a free stack at [grafana.com](https://grafana.com/auth/sign-up/create-user) (Free forever; no credit card required for Free).
2. Open your stack → **Connections** / **Prometheus** → **Send metrics** → copy **remote_write** details:
   - URL → `GRAFANA_CLOUD_PROMETHEUS_URL` (ends with `/api/prom/push`)
   - Username (instance id) → `GRAFANA_CLOUD_PROMETHEUS_USER`
   - Access policy / API token with **metrics:write** → `GRAFANA_CLOUD_API_TOKEN`
3. Add to **gitignored** `.env` (see [`.env.example`](../../.env.example)):

```bash
GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-XX-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROMETHEUS_USER=123456
GRAFANA_CLOUD_API_TOKEN=glc_...
```

4. Deploy so Alloy starts (credentials required or Alloy is skipped):

```bash
./scripts/ec2_app_deploy.sh deploy
# or after sync only — full deploy recreates Alloy:
./scripts/ec2_app_deploy.sh sync
# then recreate Alloy by re-running deploy, or SSH and start manually
```

5. In Grafana Explore, confirm series such as `node_filesystem_avail_bytes`, `container_memory_usage_bytes`, `probe_success`.

If credentials are missing, deploy logs `Alloy skipped` and removes any old `relocation-alloy` container.

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

**Runbook:** Grafana disk/RAM panels → `./scripts/ec2_app_deploy.sh status` → `logs caddy` / `logs panel` → do **not** terminate the instance (EBS `DeleteOnTermination`); prefer stop/start. Postgres lives in Docker volume `pgdata`.

---

## Related

- [ec2-panel.md](ec2-panel.md) — deploy, Caddy, stack
- [aws-postgres.md](aws-postgres.md) — Postgres on EC2
