# Agents & contributors

**All docs:** [`docs/README.md`](docs/README.md)

| I want to… | Read |
|------------|------|
| Install and use the panel | [README.md](README.md) |
| Develop / contribute | [docs/contributing.md](docs/contributing.md) |
| Run commands | [CLAUDE.md](CLAUDE.md) |

**Code:** `relocation_jobs/` (domains) · **Apps:** [`apps/`](apps/) · **Panel:** port **5051** · **Tests:** `pytest tests -o addopts= -q --tb=line`  
**Code exploration:** use **`codebase-memory-mcp`** before Grep/file reads when a task will change code (`codebase-memory` skill).  
**Tokens:** quiet commands (`npm run build --silent`, `git status -sb`); don’t dump full test/git logs; on-demand playbook: `codex-token-optimizer` skill.  
**Do not commit** unless explicitly asked. **Public repo:** no real IPs/passwords in docs — use `<ELASTIC_IP>` placeholders; secrets in gitignored `.env` / `aws-postgres.env`.

| I want to… | Go |
|------------|-----|
| Run panel / workers / MCP | [`apps/README.md`](apps/README.md) |
| Change domain logic | `relocation_jobs/<domain>/` |
