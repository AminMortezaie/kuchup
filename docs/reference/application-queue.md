# Application queue lifecycle

**Last updated:** 2026-09-24

Position-centric application queue for the panel **Applications** tab (`/applications`), MCP `list_application_queue`, and Apply transitions. Related: [business-rules.md](business-rules.md), [mcp-application.md](mcp-application.md), [catalog-pattern.md](catalog-pattern.md).

---

## Source of truth

There is **no separate queue table**. Queue membership is derived from per-user `job_tracking` in Postgres:

| Flag | Meaning |
|------|---------|
| `looking_to_apply` | User marked **Want to apply** |
| `pinned` | User pinned the role (board sort + queue) |
| `applied` | User marked applied |

**Active application queue** (invariant):

```text
(pinned OR looking_to_apply) AND NOT applied
```

Implemented once in [`positions/queue.py`](../../relocation_jobs/positions/queue.py) as `is_active_application_queue_row`. MCP and the panel Applications API both use this predicate. Do not invent a second queue store in the frontend or MCP.

Duplicate queue entries cannot exist: `job_tracking` PK is `(user_id, country, company_name, job_url)`.

---

## Lifecycle

```text
Catalog position
       │
       ├─ Want to apply  → looking_to_apply=1
       └─ Pin            → pinned=1
              │
              ▼
     Active queue  ←── panel /applications + MCP list_application_queue
              │
              ├─ MCP / Claude / Cursor: get_job_context, tailor, save_tailored_tex, render_pdf
              │
              ▼
           Apply (panel card, Job Board, or MCP mark_applied)
              │
              ├─ applied=1
              ├─ looking_to_apply=0  (date often preserved)
              └─ pinned unchanged (board may auto-pin after apply)
              │
              ▼
     Leaves active queue (because applied)
              │
              ▼
     Application history ←── /applications "Applied" tab + existing applied tracking
```

Pinning alone still puts a role in the active queue until Apply (or unpin with no looking-to-apply). Unpinning does **not** clear `looking_to_apply`. Applying does **not** require unpinning; applied rows are excluded from the active queue even if still pinned.

---

## Panel UI

| Surface | Role |
|---------|------|
| `/applications` | Position-centric list using existing `<position-card>` |
| `GET /api/applications/queue` | Hydrated board-shaped jobs in the active queue |
| `GET /api/applications/applied` | Applied history (same tracking rows, `applied=1`) |
| Job Board | Company-centric; unchanged |

Hydration lives in [`panel/application_queue.py`](../../relocation_jobs/panel/application_queue.py) — catalog job + `job_dict` / orphan `tracked_job_dict` + MCP resume badges via `load_application_summaries`.

---

## MCP

| Tool | Filter |
|------|--------|
| `list_application_queue` | Active queue predicate above |
| `list_looking_to_apply_jobs` | `looking_to_apply` only (applied already clears that flag) |
| `get_job_context.in_application_queue` | Same active-queue predicate |
| `mark_applied` | Calls `positions.service.set_job_applied` |

Tailoring does **not** require queue membership (`can_save_tailored_tex` stays true for catalog jobs).

---

## Invariants for future changes

1. Active queue = outstanding to-apply work, never applied roles.
2. UI and MCP must read the same predicate / DB state.
3. Apply from any surface (Applications, Job Board, MCP) must leave the active queue.
4. Do not hide applied rows only in the UI while leaving them in `list_application_queue`.
5. Reuse `<position-card>`; do not ship a parallel application-card design.
