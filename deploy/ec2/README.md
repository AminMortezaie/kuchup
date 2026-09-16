# EC2 deploy files

Public templates for kuchup.com (Caddy, Grafana Alloy, Tectonic warm-up) belong here.

They are **not in git yet**. `/deploy/` was gitignored before these files were added, so they exist on the operator laptop and on the EC2 host (`/home/ec2-user/relocation-jobs/deploy/ec2/`) only.

`./scripts/ec2_app_deploy.sh deploy` requires them locally (rsync copies them to the server). `check --local` warns if they are missing and still exits 0.

| File | Role |
|------|------|
| `Caddyfile` | TLS + reverse proxy for `kuchup.com` / `www` / `mcp.kuchup.com`; 404 on the raw Elastic IP |
| `config.alloy` | Grafana Alloy metrics (+ optional Loki block after `// LOKI_BEGIN`) |
| `tectonic-warm.tex` | Copied into `Dockerfile.ec2` so the first PDF render is not a network fetch |
| `grafana-dashboard-kuchup.json` | Optional dashboard import (see [monitoring.md](../../docs/operations/monitoring.md)) |
| `grafana-alert-rules.md` | Optional alert recipes |

**Before push-to-deploy:** copy these from the server or the operator laptop into git (no secrets — Alloy credentials stay in gitignored `.env`). Until then, do not enable GitHub Actions SSH deploy; a clone cannot recreate Caddy.

See [ec2-deploy.md](../../docs/operations/ec2-deploy.md).
