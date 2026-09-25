# EC2 panel production (kuchup.com)

**Domain:** [kuchup.com](https://kuchup.com) (Cloudflare)  
**Server:** same EC2 instance as Postgres + Redis (`aws-postgres.env` → `ELASTIC_IP`)  
**Status:** panel + fetch worker + Caddy on EC2

---

## Stack on EC2

| Service | Container | Port |
|---------|-----------|------|
| Postgres | `pg` | 5432 |
| Redis | `relocation-redis` | 6379 |
| Panel (gunicorn, 2 workers × 8 threads) | `relocation-panel` | 127.0.0.1:10000 |
| Remote MCP (OAuth + Streamable HTTP) | `relocation-mcp` | 127.0.0.1:10001 |
| Fetch worker (HTTP ATS scheduler) | `relocation-fetch-worker` | — |
| Playwright worker (opt-in Chromium sidecar) | `relocation-playwright-worker` | — |
| Role propagator (SQS assignments) | `relocation-role-propagator` | — |
| Caddy (TLS + reverse proxy) | `relocation-caddy` | 80, 443 |
| Grafana Alloy (optional) | `relocation-alloy` | metrics → Grafana Cloud |

Panel talks to Postgres/Redis via Docker bridge gateway `172.17.0.1` (localhost on the host). The **default fetch worker is a static Go image** (`/fetch-scheduler`): it opens fetch runs, writes HTTP work rows, fetches boards on a goroutine pool, and writes raw result rows (`ok` / `empty` / `error`). A **Python merge follower** (`relocation-fetch-merge`, panel image) reads those results and is the only writer of `matching_jobs`. Playwright/Chromium boards (`jibe`, `atlassian`, `hibob`) stay on the **opt-in sidecar**. Role propagator consumes `user-opportunity-refresh` and is the only writer of `user_opportunities` / `position_broadcast_assignments`. Remote MCP uses the same Postgres and `MCP_PUBLIC_BASE_URL=https://mcp.kuchup.com`. Alloy starts on deploy when `GRAFANA_CLOUD_*` is set in `.env` — see [monitoring.md](monitoring.md).

---

## Self-hosted runner (auto-deploy) {#self-hosted-runner}

The **Deploy** workflow (`.github/workflows/deploy.yml`) runs on a self-hosted GitHub Actions runner installed directly on the EC2 instance (`runs-on: [self-hosted, kuchup-prod]`). Being on-box means:

- No need to open EC2 SSH to GitHub's SaaS IP ranges (which change and cannot be reliably allow-listed in the security group).
- Docker builds reuse the EC2's own **BuildKit daemon cache** — no layer re-download between deploys.
- Credentials are read from the server's existing gitignored `aws-postgres.env` / `.env`; **no GitHub repository secrets needed**.

**CI** (unit tests, Go tests) stays on GitHub-hosted runners and is not affected.

### Install and register the runner

SSH onto the EC2 instance and run:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# arm64 (t4g).  Check https://github.com/actions/runner/releases for the latest version.
curl -Lo actions-runner-linux-arm64.tar.gz \
  https://github.com/actions/runner/releases/download/v2.325.0/actions-runner-linux-arm64-2.325.0.tar.gz
tar xzf actions-runner-linux-arm64.tar.gz

# Get a one-time registration token:
# GitHub → repository → Settings → Actions → Runners → New self-hosted runner
./config.sh \
  --url https://github.com/AminMortezaie/kuchup \
  --token <REGISTRATION_TOKEN> \
  --name kuchup-prod \
  --labels kuchup-prod \
  --unattended

# Install and start as a systemd user service
sudo ./svc.sh install
sudo ./svc.sh start
```

One runner per box. The concurrency group (`ec2-production-deploy`, `cancel-in-progress: false`) queues rather than cancels concurrent deploys.

### GitHub secrets

None required for deploy credentials. `aws-postgres.env` and `.env` already live on the server at `/home/ec2-user/relocation-jobs/` — the deploy script reads them via `DEPLOY_LOCAL=1`.

The runner does require a valid `GITHUB_TOKEN` to check out the repository (provided automatically by GitHub Actions for public repos).

### Triggers

| Trigger | Condition |
|---------|-----------|
| **Auto** | `workflow_run` — CI workflow completes successfully on a **push** to `main` |
| **Manual** | Actions → **Deploy** → **Run workflow** (`workflow_dispatch`); optional **Force rebuild** input |

### Memory and ops on t4g.micro

- CI runs on GitHub-hosted runners, not the EC2 — do not add test or lint steps to the Deploy workflow.
- The Deploy job runs `./scripts/ec2_app_deploy.sh deploy` with `DEPLOY_LOCAL=1` and `SKIP_STATIC_BUILD=1`. Docker image rebuilds (when Python code changes) can temporarily use **300–600 MB** RAM. Watch `./scripts/ec2_app_deploy.sh status` after a large rebuild.
- `SKIP_STATIC_BUILD=1` skips `npm run build` and `Next.js` export — these are expensive on t4g.micro and unnecessary for Python-only changes. **Static assets (`board.js`, homepage) are preserved from the last laptop deploy** and bind-mounted into the panel container. To deploy updated frontend or homepage assets, run a laptop deploy (`./scripts/ec2_app_deploy.sh deploy`) which does the full npm/Next.js build.
- Concurrency is 1: only one deploy runs at a time. If a deploy is queued when another is running, GitHub holds it until the first finishes.

### Verify after runner install

1. Repository → **Actions** → **Runners** — confirm `kuchup-prod` shows **Online**.
2. Push any commit to `main` (or **Actions → Deploy → Run workflow**).
3. Actions → **Deploy** job → confirm it runs on `kuchup-prod` (not `ubuntu-latest`) and completes green.
4. `curl -sf https://kuchup.com/api/health`

---

## Deploy / update

From repo root (SSH key `~/Downloads/relocation.pem`, `aws-postgres.env` present):

```bash
./scripts/ec2_app_deploy.sh deploy           # sync + rebuild images only when inputs change
./scripts/ec2_app_deploy.sh deploy --force   # rebuild panel + worker even if hashes match
./scripts/ec2_app_deploy.sh prune            # dangling images + trim BuildKit cache (disk recovery)
./scripts/ec2_app_deploy.sh open-sg          # one-shot: open SG 80/443 to 0.0.0.0/0 (manual)
./scripts/ec2_app_deploy.sh status           # doctor: disk/RAM, containers, /api/health, verdict
./scripts/ec2_app_deploy.sh logs panel 100   # docker logs (panel|caddy|mcp|worker|alloy|all)
./scripts/ec2_app_deploy.sh worker-logs      # follow fetch scheduler logs
./scripts/ec2_app_deploy.sh image-sizes      # compare light vs Playwright image sizes
```

**What `deploy` does**

1. Conditionally rebuilds local frontend / homepage only when sources are newer than outputs (`FORCE_FRONTEND=1` / `FORCE_HOMEPAGE=1` to force).
2. Rsyncs the repo to EC2.
3. Prunes **dangling images only** (`docker image prune -f`) — never BuildKit cache.
4. Hashes panel/worker inputs on EC2 (Dockerfiles, requirements, entrypoints, `relocation_jobs/` excluding bind-mounted `static/`). Skips `docker build` when the hash matches and the tagged image already exists.
5. Recreates panel + worker containers (static files are bind-mounted into the panel, so CSS/homepage updates apply without a panel image rebuild).
6. Recreates Caddy, starts Alloy when Grafana Cloud env is set, and runs health checks.

`deploy` does **not** call `open-sg`. After Cloudflare origin lock-down, reopening `0.0.0.0/0` on every deploy would undo the SG lockdown — run `open-sg` only when you intentionally want world-open 80/443.

**Disk (root EBS):** each rebuild can leave the previous panel/worker image dangling (~GB). `deploy` prunes dangling images before and after builds so old+new layers do not stack, but **keeps BuildKit cache** (pip / tectonic; Playwright cache only if the sidecar was built). Use `prune` alone only when the box is tight; it trims builder cache while keeping recent cache warm. Routine deploys should not need `prune` if disk is healthy. If prune still cannot free enough headroom, grow the EBS volume. Prefer keeping root usage well under ~80% — full disk has caused host hangs (`no space left on device`).

**DB safety:** prune never runs `docker volume prune`, `docker system prune --volumes`, or anything that stops/removes container `pg`. Postgres data is in named volume `pgdata`. Each prune asserts `pg` is running and `pgdata` exists before and after; it aborts if either check fails.

**Build cache:** panel and worker Dockerfiles use BuildKit cache mounts for pip. The Playwright sidecar splits the Chromium install into its own layer. Expect BuildKit (`DOCKER_BUILDKIT=1`, the deploy default). Each build also passes `--build-arg BUILDKIT_INLINE_CACHE=1` and `--cache-from <image>:ec2` so that if the BuildKit daemon cache is cold (e.g. after a Docker restart or disk-pressure GC), cached layers can still be recovered from the local image's embedded cache metadata. **Routine deploys skip the build entirely** when the content hash of Dockerfiles + requirements + source matches the saved hash on EC2 (`.deploy-hashes`) — no cache lookup needed. The Alloy container image is pulled only when not already present locally (pinned tag `v1.8.3` never changes).

| Image | Dockerfile | Role |
|-------|------------|------|
| `relocation-panel:ec2` | `Dockerfile.ec2` target `panel` | Slim panel — no Playwright, no Tectonic; `PANEL_SCRAPE_ENABLED=0`, `PANEL_COMPANY_FETCH_ENABLED=1`. Also runs the fetch merge follower. |
| `relocation-mcp:ec2` | `Dockerfile.ec2` target `mcp` | Panel layers plus Tectonic for PDF render. `relocation-mcp` uses `docker-entrypoint-mcp.sh`. |
| `relocation-fetch-worker:ec2` | `Dockerfile.ec2-worker` | **Default.** Go HTTP scheduler (`CMD /fetch-scheduler`); static binary + CA certs only — no Python in the image |
| `relocation-fetch-merge` | `relocation-panel:ec2` | Follower: `scripts/fetch_merge_consumer.py` — merge/enrich from `fetch_http_results` |
| `relocation-fetch-worker:playwright` | `Dockerfile.ec2-worker-playwright` | **Opt-in.** Chromium worker for `jibe` / `atlassian` / `hibob`; not started unless `DEPLOY_PLAYWRIGHT_WORKER=1` |

**PDF render:** the MCP image installs pinned tectonic and warms its package cache at build time. After deploy, smoke with `docker exec relocation-mcp tectonic --version`, then **Re-render PDF** on a master or company workspace on [kuchup.com](https://kuchup.com).

Manual country scrape from your laptop still works (`PANEL_SCRAPE_ENABLED=1`); the worker skips a cycle if another fetch is already running (`fetch_runs.status = running`). Light and Playwright workers share that lock — do not run both loops on the same 6h cadence unless you accept skipped cycles.

**Panel company fetch:** `POST /api/companies/fetch` (board **Fetch jobs**) runs in the panel process when `PANEL_COMPANY_FETCH_ENABLED=1`. Country-wide `/api/fetch` stays off on the slim panel. Playwright-only ATS boards still need the Playwright sidecar or a local scrape with Chromium. The light worker skips those companies (no empty-board merge / `ImportError`).

**Worker env (Go scheduler):** `FETCH_SCHEDULE_ENABLED=1`, `FETCH_SCHEDULE_INTERVAL_HOURS=6`, `FETCH_HTTP_POOL_SIZE=4` (ceiling 16), `FETCH_WORKER_KIND=http`, `DATABASE_URL`. Optional: `FETCH_SCHEDULE_COUNTRIES=uk,netherlands`. **Merge follower:** `FETCH_MERGE_POLL_SECONDS=2` on `relocation-fetch-merge`. Listing check is **not** run on the Go worker (still available on manual Python scheduler paths).

```text
Go image entry point (/fetch-scheduler)
        │
        ▼
 open fetch run → write fetch_http_work → goroutine pool → fetch_http_results → close run
        │
        ▼
 Python merge follower (panel image)
        │
        ▼
 matching_jobs
```

Result `status`: `ok` (jobs JSON), `empty` (zero jobs, successful scrape), `error` (failed fetch — merge marks `fetch_problem`, no merge). A finished run’s `result_line` notes **merge pending** until the follower catches up.

Go startup runs `EnsureSchema` for `fetch_http_work` / `fetch_http_results` (idempotent). Stale **`running`** rows older than `FETCH_COUNTRY_TIMEOUT_SECONDS` (default 2700) are marked failed on each cycle — not every `running` row on boot (panel company fetches stay safe).

### Worker memory caps

`scripts/ec2_app_deploy.sh` sets `--memory` and `--memory-swap` to the same value, so the container gets no extra swap:

| Container | Cap | Why |
|-----------|-----|-----|
| `relocation-fetch-worker` | **256m** | Static Go scheduler + HTTP pool (no Chromium, no CPython). |
| `relocation-playwright-worker` | **640m** | One browser (concurrency 1). Hard ceiling under the ~837MiB max that pressured the ~2GiB host. |

Postgres, Redis, panel, MCP, role propagator, Caddy, and Alloy are unchanged in this deploy path.

If a worker hits its cap, the kernel OOM-kills that container (exit 137). `--restart unless-stopped` starts it again. The in-flight country cycle is lost and the next 6h pass retries. That is the tradeoff: a killed worker beats a wedged host (SSH timeout / Cloudflare 522). `./scripts/ec2_app_deploy.sh status` prints `oom=` from `State.OOMKilled`.

On `t4g.micro`, tune **`FETCH_HTTP_POOL_SIZE`** (not the old Python `FETCH_SCHEDULE_CONCURRENCY=2`). The Playwright sidecar, when enabled, uses concurrency **1**. History: [fetch-thread-exhaustion-incident.md](../archive/fetch-thread-exhaustion-incident.md).

### Light vs Playwright images

Routine deploy builds the light image only and removes the sidecar. `image-sizes` (above) compares them. The light image drops Chromium and its OS deps — typically **~300–500MB**.

```bash
DEPLOY_PLAYWRIGHT_WORKER=1 ./scripts/ec2_app_deploy.sh deploy --force
FETCH_WORKER_KIND=http FETCH_SCHEDULE_ENABLED=1 python3 apps/fetch-worker/run.py --once
FETCH_SCHEDULE_ENABLED=1 python3 apps/playwright-worker/run.py --once
```

**Most companies flagged `fetch_problem` but cycles finish in ~1s?** That was thread exhaustion (`can't start new thread`) before the 2026-09-02 concurrency change — not ATS breakage. Look at `company_fetch_attempts.error_message`, not Grafana. Restart: `docker restart relocation-fetch-worker`. Durable logs survive in Postgres; `docker logs` are wiped on deploy.

**Scheduler stuck?** If `worker-logs` shows no new lines for 2+ hours while the container is Up, an HTTP scrape may have hung (or the opt-in Playwright sidecar, if running). Restart: `docker restart relocation-fetch-worker` (and `relocation-playwright-worker` if you started it). Timeouts: `FETCH_COMPANY_TIMEOUT_SECONDS=300`, `FETCH_COUNTRY_TIMEOUT_SECONDS=2700`, `PLAYWRIGHT_BOARD_TIMEOUT_SECONDS=90` ([architecture.md](../reference/architecture.md#fetch)). Incident history: [fetch-scheduler-timeout-practices.md](../archive/fetch-scheduler-timeout-practices.md).

---

## Cloudflare DNS

Point the domain at the Elastic IP from `aws-postgres.env`:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `<ELASTIC_IP>` | start grey; orange when locking origin (below) |
| A | `www` | `<ELASTIC_IP>` | same |
| A | `mcp` | `<ELASTIC_IP>` | same (remote MCP for Claude / Cursor) |

Domain email (`hello@` / `support@`) uses Cloudflare Email Routing — see [email.md](email.md). Do not orange-proxy MX or mail TXT records.

Caddy config lives in **gitignored** `deploy/ec2/Caddyfile` (not in the public tree). It requests Let's Encrypt certs for `kuchup.com`, `www.kuchup.com`, and `mcp.kuchup.com`. The panel and MCP are **not** served on the raw Elastic IP — use the domain only.

**Claude remote connectors** reach `mcp.kuchup.com` from Anthropic’s cloud (not the user’s phone). If the security group is locked to Cloudflare only, that is enough when the orange cloud proxies MCP. If you later lock origin beyond Cloudflare, also allowlist [Anthropic egress ranges](https://platform.claude.com/docs/en/api/ip-addresses).

**First cutover (simplest):** grey cloud (DNS only) until `https://kuchup.com` works.

**Cloudflare SSL (orange cloud):** **SSL/TLS** → **Full** or **Full (strict)** (never **Flexible**).

Verify:

```bash
dig +short kuchup.com A
curl -I https://kuchup.com
```

---

## Lock down origin (domain only, hide IP)

Goal: users reach the panel via `https://kuchup.com` only; casual access to `http://<ELASTIC_IP>` is blocked.

| Layer | What it does |
|-------|----------------|
| **Caddy** | Explicit 404 on the Elastic IP — only `kuchup.com` / `www` proxy to the panel |
| **Cloudflare proxy** | Orange cloud hides origin IP from public DNS (`dig` shows Cloudflare IPs) |
| **AWS security group** | Ports 80/443 accept traffic **only from Cloudflare**, not `0.0.0.0/0` |

The origin IP can still be discovered (old DNS, scans, leaks). Treat this as **not advertising** the IP, not making it impossible to find.

### 1. Caddy (done in repo)

Gitignored `deploy/ec2/Caddyfile` returns **404** for `http://<ELASTIC_IP>`; only the domain proxies to the panel. After changing it:

```bash
./scripts/ec2_app_deploy.sh sync
ssh -i ~/Downloads/relocation.pem ec2-user@<ELASTIC_IP> 'docker restart relocation-caddy'
```

### 2. Cloudflare — enable proxy

**DNS → Records:** set `@` and `www` to **Proxied** (orange cloud).

**SSL/TLS → Overview:** **Full** or **Full (strict)**.

### 3. AWS — restrict 80/443 to Cloudflare

In **EC2 → Security Groups** (panel instance), for inbound **HTTP (80)** and **HTTPS (443)**:

1. Remove rules with source `0.0.0.0/0`.
2. Add rules with source = [Cloudflare IPv4 ranges](https://www.cloudflare.com/ips-v4) (and [IPv6](https://www.cloudflare.com/ips-v6) if you use AAAA).

**Do not** open 80/443 to the world again. `./scripts/ec2_app_deploy.sh open-sg` adds `0.0.0.0/0` — it is not part of `deploy`; run it only for initial bootstrap, then remove those rules after Cloudflare lock-down.

**Keep separate (your IP only, never `0.0.0.0/0`):**

- SSH **22**
- Postgres **5432** (local dev / Render if still used)
- Redis **6379** (if accessed off-box)

Example (replace `sg-…` and region; IPv4 list changes — fetch current ranges from Cloudflare):

```bash
# Remove public web (if present)
aws ec2 revoke-security-group-ingress --region eu-central-1 --group-id sg-XXXXXXXX \
  --ip-permissions 'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0}]'
aws ec2 revoke-security-group-ingress --region eu-central-1 --group-id sg-XXXXXXXX \
  --ip-permissions 'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]'

# Allow Cloudflare (repeat per CIDR from https://www.cloudflare.com/ips-v4)
aws ec2 authorize-security-group-ingress --region eu-central-1 --group-id sg-XXXXXXXX \
  --ip-permissions 'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=173.245.48.0/20,Description=cloudflare}]'
# …same for 443 and remaining Cloudflare CIDRs
```

### 4. Verify lock-down

```bash
curl -I https://kuchup.com                    # 200 / redirect — OK
curl -I http://<ELASTIC_IP> --max-time 5    # timeout or refused — OK
dig +short kuchup.com A                     # Cloudflare IPs when proxied
```

Health checks after lock-down: use the domain, not the Elastic IP:

```bash
curl -sf https://kuchup.com/api/health
```

---

## Incident: Cloudflare 522 / host hung

Cloudflare **522** means the origin timed out or refused — not an application 5xx.

```bash
./scripts/ec2_app_deploy.sh status
./scripts/ec2_app_deploy.sh logs caddy 100
./scripts/ec2_app_deploy.sh logs panel 100
```

| `status` observation | Likely layer |
|----------------------|--------------|
| Panel localhost **200**, domain fail | Cloudflare ↔ Caddy / SG |
| Panel localhost fail / Exited | Panel or Caddy down |
| Up but hang / SSH banner timeout | Host wedged (disk or memory) |

Known causes: Docker filling the root volume; fetch-worker memory pressure. Caps and the OOM-restart tradeoff: [Worker memory caps](#worker-memory-caps). Prefer **stop/start** over terminate (EBS may have `DeleteOnTermination`). Full monitoring runbook: [monitoring.md](monitoring.md).

---

## Environment on server

Set via `ec2_app_deploy.sh` (from local `.env` / `aws-postgres.env`):

- `DATABASE_URL` → `172.17.0.1:5432`
- `REDIS_URL` → `172.17.0.1:6379`
- `PANEL_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PANEL_ADMIN_EMAILS`
- Optional staff admin passwords: `PANEL_STAFF_LOGINS` (see [Staff admin login](#staff-admin-login))
- Checkout: `NOWPAYMENTS_API_KEY`, `NOWPAYMENTS_IPN_SECRET` (see [nowpayments.md](nowpayments.md))
- Optional: `GRAFANA_CLOUD_PROMETHEUS_URL`, `GRAFANA_CLOUD_PROMETHEUS_USER`, `GRAFANA_CLOUD_API_TOKEN` (starts Alloy)
- Optional logs: `GRAFANA_CLOUD_LOKI_URL`, `GRAFANA_CLOUD_LOKI_USER` (same token needs `logs:write`; see [monitoring.md](monitoring.md))

Do not commit production secrets. Rotate `PANEL_SECRET_KEY` to a long random value in `.env` before deploy if still using the placeholder.

---

## Staff admin login

Teammates without a Google address on `PANEL_ADMIN_EMAILS` can sign in at `https://kuchup.com/admin` with email + password. Amin's Google admin path is unchanged. `/admin` is `Disallow` in `robots.txt` and sends `noindex, nofollow`.

Google Workspace `@kuchup.com` emails remain a valid longer-term option: add them to `PANEL_ADMIN_EMAILS` and they can use Continue with Google. This env list is the code unblock until those accounts exist.

### Add a staff user (Kio, Figo, …)

1. Ask them which email they will type on `/admin` (personal is fine).
2. Generate a hash locally — do not commit it:

```bash
python3 scripts/hash_staff_password.py
```

3. Put the hash in gitignored `.env` (comma-separated, `email:hash`):

```bash
PANEL_STAFF_LOGINS=kio@example.com:pbkdf2:sha256:600000$...,figo@example.com:pbkdf2:sha256:600000$...
```

4. Redeploy so the panel container receives the var: `./scripts/ec2_app_deploy.sh deploy`
5. They open `https://kuchup.com/admin`, enter that email and the password you hashed, then use admin (including Docs once team docs are deployed).

To revoke: remove their `email:hash` from `PANEL_STAFF_LOGINS` and redeploy. Existing sessions last until the cookie expires; they cannot sign in again.

---

## SSH

Searchable history: Grafana Explore → Loki (`{name="relocation-panel"}`) — [monitoring.md](monitoring.md). Live tail:

```bash
cd ~/Downloads
ssh -i relocation.pem ec2-user@<ELASTIC_IP>
docker ps
docker logs relocation-panel --tail 50
docker logs relocation-fetch-worker --tail 50
docker logs relocation-playwright-worker --tail 50
docker logs relocation-caddy --tail 50
```

---

## Related

- [monitoring.md](monitoring.md) — Grafana Cloud Free, Alloy, alerts, 522 runbook
- [nowpayments.md](nowpayments.md) — credit packs + Full Access checkout
- [aws-postgres.md](aws-postgres.md) — Postgres on EC2
- `scripts/ec2_redis.sh` — Redis on EC2
- [board-read-model-proposal.md](../proposals/board-read-model-proposal.md) — board performance (still the main latency fix)
