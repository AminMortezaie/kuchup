# Agents & contributors

Technical docs live in the admin panel: **Admin Docs → Tech**.

| I want to… | Read |
|------------|------|
| Install and use the panel | [README.md](README.md) |
| Run panel / workers / MCP | [`apps/README.md`](apps/README.md) |

**Code:** `relocation_jobs/` (Python domains) · `role_propagator/` (Go assignments) · **Apps:** [`apps/`](apps/) · **Panel:** port **5051** · **Tests:** `pytest tests -o addopts= -q --tb=line`  
**Code exploration:** use **`codebase-memory-mcp`** before Grep/file reads when a task will change code (`codebase-memory` skill).  
**Tokens:** quiet commands (`npm run build --silent`, `git status -sb`); don’t dump full test/git logs; on-demand playbook: `codex-token-optimizer` skill.  
**Do not commit** unless explicitly asked. **Public repo:** no real IPs/passwords in docs — use `<ELASTIC_IP>` placeholders; secrets in gitignored `.env` / `aws-postgres.env`.

| I want to… | Go |
|------------|-----|
| Change domain logic | `relocation_jobs/<domain>/` (Python) · `role_propagator/` (Go) |
| Production ops | Admin Docs → Tech → EC2 panel production |
