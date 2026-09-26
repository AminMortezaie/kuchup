# Kuchup load testing (k6)

Capacity-style load tests for the **live Kuchup product**: separate load generator, realistic think time, ramp virtual users (VUs) until thresholds fail. Scripts hit real panel HTML, authenticated board APIs, and **low-rate pin / looking-to-apply (LTA) writes** on a **dedicated test account**.

This is **not** a demo API and **not** wired into CI — nothing here runs a production ramp automatically.

## Before you run against production

1. **Wait for Amin to paste and confirm the exact `BASE_URL`** for the load-test window (may be `https://kuchup.com` or another host).
2. Do **not** set `FULL_RAMP=1` until that URL is confirmed and you have a **dedicated load-test account** (not your personal production data).
3. Default stages are a **soft ramp** (5 → 10 → 25 → 50 VUs) so a first prod run cannot jump straight to thousands of VUs.

Examples in this doc use `https://kuchup.com` as a placeholder only.

## Layout

| Path | Purpose |
|------|---------|
| `k6/kuchup-load.js` | Main scenario (HTML + board API + pin/LTA toggles) |

## 1. Where to run k6

Prefer a **dedicated load-gen VM** in the **same region** as the app. Use a laptop only for **`SMOKE=1`** (public HTML, no auth).

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

## 3. Smoke test (public HTML only)

No session cookie: exercises `/`, `/panel`, `/remote`, company HTML. **2 VUs, ~45s.** Aborts only on **error rate**, not latency.

```bash
cd /path/to/kuchup
SMOKE=1 BASE_URL=https://kuchup.com k6 run load-test/k6/kuchup-load.js
```

Use the `BASE_URL` Amin confirms when testing production.

## 4. Authenticated runs (test account)

Production load tests should use a **dedicated test account** whose pin/LTA toggles are safe to flip repeatedly. **Never commit** cookies or passwords.

### Preferred: `AUTH_COOKIE`

1. Log in to Kuchup as the **load-test account** (browser).
2. DevTools → **Application** / **Storage** → **Cookies** → your `BASE_URL` host.
3. Copy the **`Cookie` header** the browser sends (session cookies).
4. On the load-gen VM only:

```bash
export AUTH_COOKIE='session=...; ...'
export BASE_URL='https://kuchup.com'   # use Amin-confirmed value
k6 run load-test/k6/kuchup-load.js
```

Optional: store vars in a gitignored file outside the repo (`chmod 600`).

### Optional: email + password (staff login API only)

If the test account is listed in server **`PANEL_STAFF_LOGINS`**, k6 can obtain a session once in `setup()` via:

`POST /api/auth/staff` with JSON `{ "email", "password" }` (see `relocation_jobs/web/routes/auth.py`).

```bash
export KUCHUP_EMAIL='loadtest@example.com'
export KUCHUP_PASSWORD='...'
export BASE_URL='...'
k6 run load-test/k6/kuchup-load.js
```

Google OAuth has **no** headless login in this harness — use **`AUTH_COOKIE`** from a browser session for normal user accounts.

## 5. Ramps and thresholds

| Mode | Env | Stages |
|------|-----|--------|
| Smoke | `SMOKE=1` | 2 VUs, 45s |
| **Default (prod-safe)** | *(none)* | **5 → 10 → 25 → 50** VUs (1–2 min holds) |
| Aggressive | `FULL_RAMP=1` | **10 → 50 → 100 → 200 → 500 → 1000 → 2000** (2 min each) |

Use **`FULL_RAMP=1` only after Amin confirms `BASE_URL`** and you have watched at least one soft ramp.

Non-smoke thresholds (abort the run on breach):

- `http_req_duration` **p(95) ≤ 500ms**
- `http_req_failed` **rate ≤ 1%**

```bash
# Soft ramp + auth (typical first prod run)
AUTH_COOKIE='...' BASE_URL='...' k6 run load-test/k6/kuchup-load.js

# Capacity ramp (explicit)
FULL_RAMP=1 AUTH_COOKIE='...' BASE_URL='...' k6 run load-test/k6/kuchup-load.js
```

## 6. Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `BASE_URL` | `https://kuchup.com` | Origin (no trailing slash) — **confirm with Amin before prod** |
| `SMOKE` | unset | `1` = public HTML smoke |
| `FULL_RAMP` | unset | `1` = aggressive 10→2000 stages |
| `AUTH_COOKIE` | empty | Session cookie header (preferred) |
| `KUCHUP_EMAIL` / `KUCHUP_PASSWORD` | empty | Optional staff login → session (see above) |
| `COUNTRY_RELOCATION` | `armenia` | Relocation panel country |
| `COUNTRY_REMOTE` | `remote-ok` | Remote board country slug |
| `COMPANY_REMOTE_SLUG` | `winatalent` | Public company workspace |
| `COMPANY_ARMENIA_SLUG` | empty | Optional Armenia company HTML when unauthenticated |
| `TIMEZONE_RELOCATION` | `Asia/Yerevan` | Board `timezone` param |
| `TIMEZONE_REMOTE` | `UTC` | Remote board `timezone` |

Board query flags match **`boardQueryParams()`** defaults in `relocation_jobs/static/js/api.js`. Remote board uses **`/api/remote/board`** (`panelApiPrefix()` in `panel-mode.js`).

## 7. What the VU loop does

Per iteration (~15–25s think time):

1. Occasionally `GET /`; alternate `GET /panel?country=…` and `GET /remote?country=…`
2. Sleep 3–7s
3. **With auth:** `GET /api/board` or `GET /api/remote/board`; **without auth:** `GET /company/…`
4. Sleep 3–8s
5. **With auth:** `GET …/board/company-roles` for a company from the board
6. **With auth (~2% each, independent rolls):** POST pin + PATCH unpin; POST LTA on + PATCH LTA off (`/api/jobs/looking-to-apply`) on jobs from the board — same iteration restores state
7. Occasionally `GET /api/health`; sleep 5–15s

Requests are tagged (`name`) for k6 summaries.

## 8. Watch the **app** host during a run

```bash
docker stats --no-stream
watch -n5 'free -h; uptime'
```

Also: `GET …/api/health`, Grafana/Alloy (`docs/operations/monitoring.md`), `./scripts/ec2_app_deploy.sh status`.

## 9. Safety

- Production load tests can hurt real users. **Do not run soft or full ramp until Amin confirms `BASE_URL`.**
- Use a **dedicated test account** for auth runs; pin/LTA toggles are intentional but low-rate (~2% per mutation type per iteration).
- Do not commit secrets. This repo is public.

## 10. Report template

| Field | Example |
|-------|---------|
| `BASE_URL` used | (confirmed with Amin) |
| Ramp mode | soft / `FULL_RAMP=1` |
| Peak VUs before abort | 50 |
| Approx RPS | from k6 `http_reqs` |
| p95 / error % | k6 summary |
| App CPU / RAM | `docker stats` / Grafana |
| Auth | test account cookie / staff login |

Redirect logs: `k6 run ... 2>&1 | tee load-run-$(date +%F).log`.
