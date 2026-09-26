# Kuchup load testing (k6)

Capacity-style load tests for the **live Kuchup product** (`https://kuchup.com`): separate load generator, realistic think time, ramp virtual users (VUs) until thresholds fail. This is **not** a demo API — scripts hit real panel HTML and authenticated board APIs.

## Layout

| Path | Purpose |
|------|---------|
| `k6/kuchup-load.js` | Main scenario (HTML + optional auth API + optional pin toggle) |

## 1. Where to run k6

Prefer a **dedicated load-gen VM** in the **same region** as the app (low latency, isolated CPU). Use your laptop only for **smoke** runs (`SMOKE=1`).

Do **not** run large ramps from CI against production without explicit approval.

## 2. Install k6

On Debian/Ubuntu (load-gen VM):

```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

See [k6 installation docs](https://grafana.com/docs/k6/latest/set-up/install-k6/) for other OSes.

## 3. Smoke test (public HTML, no auth)

Confirms paths and thresholds against production **without** session cookie. Uses 2 VUs for ~45s.

```bash
cd /path/to/kuchup
SMOKE=1 BASE_URL=https://kuchup.com k6 run load-test/k6/kuchup-load.js
```

Expected: `http_req_failed` well under 1% (smoke **aborts** on error rate). Latency is reported but smoke does not abort on `p(95)` — run smoke from the app region or accept higher RTT from elsewhere. Full ramp uses **abortOnFail** on both latency and errors.

Full ramp (production — coordinate with Amin first):

```bash
BASE_URL=https://kuchup.com k6 run load-test/k6/kuchup-load.js
```

Stages: **10 → 50 → 100 → 200 → 500 → 1000 → 2000** VUs, **2 minutes** each, until `p(95) > 500ms` or **error rate > 1%** stops the test.

## 4. Authenticated board API

Board JSON requires a logged-in session (`@login_required` on `/api/board`). Remote board uses **`/api/remote/board`** (see `panelApiPrefix()` in `relocation_jobs/static/js/panel-mode.js`).

Query defaults match **`boardQueryParams()`** in `relocation_jobs/static/js/api.js` (filters off → `0`, `page=1`, `page_size=25`, `sort=newest`, plus `timezone`).

### Capture `AUTH_COOKIE` safely

1. Log in to Kuchup in a browser.
2. DevTools → **Application** (or **Storage**) → **Cookies** → `https://kuchup.com`.
3. Copy the **full** `Cookie` header value your browser sends (session cookie name + value), **or** paste `name=value; ...` for the session cookies only.
4. Export on the load-gen VM only — **never commit**, never paste into tickets/PRs:

```bash
export AUTH_COOKIE='session=...; other=...'
BASE_URL=https://kuchup.com k6 run load-test/k6/kuchup-load.js
```

Optional: pass via env file outside the repo (`chmod 600`) and `set -a; source ~/kuchup-load.env; set +a`.

## 5. Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `BASE_URL` | `https://kuchup.com` | Origin (no trailing slash) |
| `SMOKE` | unset | `1` = short 2-VU smoke stages |
| `AUTH_COOKIE` | empty | Session cookie header for API paths |
| `ENABLE_MUTATIONS` | `0` | `1` = ~2% of iterations POST pin + PATCH unpin (requires auth) |
| `COUNTRY_RELOCATION` | `armenia` | Relocation panel country |
| `COUNTRY_REMOTE` | `remote-ok` | Remote board country slug |
| `COMPANY_REMOTE_SLUG` | `winatalent` | Public company workspace |
| `COMPANY_ARMENIA_SLUG` | empty | Optional `/company/armenia/<slug>` when unauthenticated |
| `TIMEZONE_RELOCATION` | `Asia/Yerevan` | Board `timezone` param |
| `TIMEZONE_REMOTE` | `UTC` | Remote board `timezone` |

Mutations (off by default):

```bash
ENABLE_MUTATIONS=1 AUTH_COOKIE='...' SMOKE=1 BASE_URL=https://kuchup.com k6 run load-test/k6/kuchup-load.js
```

Pin/unpin uses the same job from the board response in that iteration (minimal state churn).

## 6. What the VU loop does

Per iteration (~15–25s think time, ~0.1 req/s/VU feel):

1. Occasionally `GET /`; alternate `GET /panel?country=…` and `GET /remote?country=…`
2. Sleep 3–7s
3. With `AUTH_COOKIE`: `GET /api/board` or `GET /api/remote/board`; else `GET /company/…`
4. Sleep 3–8s
5. With auth: `GET …/board/company-roles` for a company from the board; else `GET /company/remote-ok/winatalent`
6. If `ENABLE_MUTATIONS=1`: rare pin then unpin on `/api/jobs/pin`
7. Occasionally `GET /api/health`; sleep 5–15s

Requests are tagged (`name` tag) for readable k6 summaries.

## 7. Watch the **app** host during a run

On the EC2 / Docker host running the panel (not on the load-gen VM):

```bash
docker stats --no-stream
watch -n5 'free -h; uptime'
```

Operational probes already used in production:

- `GET https://kuchup.com/api/health` — Postgres + Redis; **200** or **503**
- Grafana / Alloy host & container metrics (see `docs/operations/monitoring.md`)
- `./scripts/ec2_app_deploy.sh status` — disk, RAM, containers, health verdict

Watch **`relocation-panel`** (or equivalent panel container) CPU % and RSS, Postgres connections, and load average (`uptime`).

## 8. Safety

- Production load tests can **degrade service for real users**. Confirm **`BASE_URL`** and timing with **Amin** before large ramps.
- Start with **`SMOKE=1`**, then small manual VU overrides if you edit stages.
- Keep **`ENABLE_MUTATIONS=0`** unless you intentionally stress write paths.
- Do not commit real cookies, IPs, or passwords (public repo).

## 9. Report template

After a run, capture:

| Field | Example |
|-------|---------|
| Peak VUs before abort | 200 |
| Approx RPS | `http_reqs` / duration from k6 summary |
| p95 latency | k6 `http_req_duration` p(95) |
| Error rate | `http_req_failed` rate |
| App CPU / RAM | peak from `docker stats` / Grafana |
| Notes | region, auth on/off, mutations on/off |

k6 writes a end-of-run summary to stdout; redirect if needed: `k6 run ... 2>&1 | tee load-run-$(date +%F).log`.
