# EC2 deploy flow (kuchup.com)

**Status:** laptop → SSH/rsync. Not git-push auto-deploy.  
**Do not merge without Amin’s approval.**  
**Secrets:** never commit `aws-postgres.env`, `.env`, `*.pem`, or live `DATABASE_URL`.

Day-to-day commands and Cloudflare lock-down: [ec2-panel.md](ec2-panel.md). Monitoring: [monitoring.md](monitoring.md).

---

## What production deploy is today

From a machine that has gitignored `aws-postgres.env` and `~/Downloads/relocation.pem`:

```bash
./scripts/ec2_app_deploy.sh check            # plan: hashes, would rebuild vs skip, no writes
./scripts/ec2_app_deploy.sh check --local    # same, no SSH (CI)
./scripts/ec2_app_deploy.sh deploy --dry-run # alias of check when you pass the flag to deploy
./scripts/ec2_app_deploy.sh sync --dry-run   # rsync -n
./scripts/ec2_app_deploy.sh deploy           # real deploy
```

`deploy` phases (logged with elapsed seconds; summary at the end):

1. **Preflight** — SSH, `Dockerfile.ec2*`, local `deploy/ec2/Caddyfile`, Postgres container `pg` running, volume `pgdata` present, root disk under 95% (warn at 85%). Aborts before any container swap if a guard fails.
2. **Frontend / homepage** — content hash of sources vs `.source-hash` stamps (not `find -newer`). Skip when the stamp matches and the output file exists. `FORCE_FRONTEND=1` / `FORCE_HOMEPAGE=1` to force.
3. **Sync** — rsync the repo (excludes `.git`, `.env`, `aws-postgres.env`, `node_modules`, `.deploy-hashes`).
4. **Prune dangling images** — `docker image prune -f` only. Never BuildKit cache, never volumes, never `pg`.
5. **Build images** (panel, worker, optional propagator, optional Playwright sidecar) **before** any `docker rm` of app containers. Hash skip if inputs and the tagged image match.
6. **Swap app containers** — panel, MCP, worker, optional propagator / Playwright sidecar, Caddy, Alloy. Does not stop or recreate `pg` or `relocation-redis`.
7. **Prune dangling images again**, then `status` + summary (rebuilt vs skipped).

Image hashes include `.dockerignore` and omit bind-mounted `relocation_jobs/static/`. CSS/homepage updates apply without a panel image rebuild.

---

## Safety rails

| Guard | Behavior |
|-------|----------|
| `pg` / `pgdata` | Asserted before prune, before image builds, and before container swap. Missing or stopped → abort. |
| Protected names | Script refuses to treat `pg`, `postgres`, `relocation-redis`, or `pgdata` as an app container. |
| Disk | ≥95% root usage aborts before builds; ≥85% warns. |
| Prune | Dangling images only. Manual `prune` may trim BuildKit cache (`--keep-storage 8GB`). No `docker volume prune`, no `docker system prune --volumes`. |
| Secrets on the wire | Env values passed into `docker run` are `printf %q`-quoted so passwords with quotes do not break the remote script. |

`deploy/ec2/Caddyfile`, `config.alloy`, and `tectonic-warm.tex` are still **operator-local** (see [deploy/ec2/README.md](../../deploy/ec2/README.md)). A fresh clone can run `check --local` but cannot complete a real deploy until those files are present.

---

## Light vs Playwright worker (PR #6)

Open PR #6 splits the default EC2 worker (HTTP ATS) from an opt-in Chromium sidecar (`Dockerfile.ec2-worker-playwright`, `DEPLOY_PLAYWRIGHT_WORKER=1`).

This tree on `main` still ships Playwright inside `Dockerfile.ec2-worker`. The deploy script already has the sidecar hook:

- If the Playwright Dockerfile is **absent** (today): log and skip; `DEPLOY_PLAYWRIGHT_WORKER=1` errors instead of building a missing file.
- If PR #6 **lands**: `DEPLOY_PLAYWRIGHT_WORKER=1` builds/runs `relocation-playwright-worker`. Routine deploys leave it off and remove a leftover sidecar.

Do not run both 6h loops on `t4g.micro` unless you accept skipped cycles (`fetch_runs.status = running` is shared).

---

## GitHub Actions

| Workflow | What it does |
|----------|----------------|
| [`ci.yml`](../../.github/workflows/ci.yml) `deploy-sanity` | `shellcheck` on the deploy script + `./scripts/ec2_app_deploy.sh check --local` |
| [`ec2-deploy.yml`](../../.github/workflows/ec2-deploy.yml) | **Stub.** `workflow_dispatch` only. No `on: push`, no SSH, no secrets. Re-runs the local check. |

Nothing in CI SSHes to EC2 or copies `.env`.

---

## Roadmap: push-to-deploy (not this PR)

Do not enable automatic EC2 deploy on git push until Amin explicitly turns it on.

Suggested order:

1. **Track `deploy/ec2/` in git** (Caddyfile, Alloy, tectonic-warm). No secrets in those files — Alloy uses env at container start.
2. **GitHub Environment `production`** with required reviewers (Amin). Store `EC2_SSH_KEY`, `ELASTIC_IP` (or SSM), never in the repo.
3. **Job steps:** `check --local` → SSH `check` / `deploy --dry-run` → **manual approval** → `deploy`. First enablement should be `workflow_dispatch` only, still not `on: push`.
4. **Then** (optional) `on: push` to `main` with the same approval gate — or keep dispatch-only.
5. **Never** rsync `.env` / `aws-postgres.env` from Actions. Inject env from GitHub secrets or SSM into `docker run`, same as the laptop script does today.

Until (1) and (2) exist, a GitHub-hosted runner cannot recreate production Caddy and must not be given a world-reachable SSH key without an approval gate.
