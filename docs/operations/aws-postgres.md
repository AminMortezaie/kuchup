# AWS Postgres (EC2)

**Status:** live  
**Host:** Docker `pg` on the same EC2 instance as the panel (`eu-central-1`)  
**State file:** gitignored `aws-postgres.env` (Elastic IP, instance ID, password)

Postgres is the catalog and tracking source of truth. Neon cutover is done — history: [neon-to-aws-postgres-migration.md](../archive/neon-to-aws-postgres-migration.md).

---

## Day-to-day

Ops script: `scripts/aws_postgres_migrate.sh` (name is leftover from the migration; these commands are still used).

| Command | When |
|---------|------|
| `./scripts/aws_postgres_migrate.sh sync-sg` | After your public IP changes (opens SSH 22 + Postgres 5432 for that IP) |
| `./scripts/aws_postgres_migrate.sh status` | Instance + Postgres reachability |
| `./scripts/aws_postgres_migrate.sh ensure-eip` | Elastic IP missing / `DATABASE_URL` host drifted |
| `./scripts/aws_postgres_migrate.sh backup-hint` | Print the daily `pg_dump` cron one-liner |

Production panel/worker containers talk to Postgres on the Docker bridge: `172.17.0.1:5432`. Laptop/dev uses `DATABASE_URL` with host `<ELASTIC_IP>` from `aws-postgres.env`.

```bash
# example only — real values stay in gitignored .env
DATABASE_URL=postgresql://relocation:PASSWORD@<ELASTIC_IP>:5432/relocation_jobs?sslmode=prefer
```

Pool: `psycopg_pool.ConnectionPool` in `relocation_jobs/core/db.py` (`min_size=2`, `max_size=8` per gunicorn worker).

---

## Backups

On the EC2 host (do not commit dump paths with live hosts):

```bash
docker exec pg pg_dump -U relocation relocation_jobs | gzip > /home/ubuntu/backups/$(date +%F).sql.gz
```

`./scripts/aws_postgres_migrate.sh backup-hint` prints the crontab line.

---

## Related

- [ec2-panel.md](ec2-panel.md) — panel + worker + Caddy on this host
- [contributing.md](../contributing.md) — local `DATABASE_URL`
- [`relocation_jobs/core/db.py`](../../relocation_jobs/core/db.py)
