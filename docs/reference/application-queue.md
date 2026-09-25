# Application queue lifecycle

**Last updated:** 2026-09-25

Position-centric application states for the panel **Applications** tab (`/applications`), MCP `list_application_queue`, and Apply transitions. Related: [business-rules.md](business-rules.md), [mcp-application.md](mcp-application.md), [catalog-pattern.md](catalog-pattern.md).

---

## Source of truth

There is **no separate queue table**. Membership is derived from per-user `job_tracking` in Postgres:

| Flag | Meaning |
|------|---------|
| `looking_to_apply` | User marked **Want to apply** |
| `pinned` | User pinned the role (board sort + queue) |
| `applied` | User marked applied |
| `rejected` | Application received a rejection |

**Application states** (panel Applications tabs):

| State | Predicate | API |
|-------|-----------|-----|
| **Apply** | `(pinned OR looking_to_apply) AND NOT applied` | `GET /api/applications/queue` |
| **Applied** | `applied AND NOT rejected AND NOT not_for_me` | `GET /api/applications/applied` |
| **Rejected** | `applied AND rejected AND NOT not_for_me` | `GET /api/applications/rejected` |

Active queue predicate is implemented once in [`positions/queue.py`](../../relocation_jobs/positions/queue.py) as `is_active_application_queue_row` (plus `is_active_applied_row` / `is_rejected_application_row`). MCP `list_application_queue` and the panel Apply tab share the Apply predicate. Do not invent a second queue store in the frontend or MCP.

Duplicate queue entries cannot exist: `job_tracking` PK is `(user_id, country, company_name, job_url)`.

---

## Counts vs lists

```text
                 Applications
                      │
             ┌────────┴────────┐
             │                 │
           Counts          Position Lists
      GET /api/applications/counts
                               │
                  ┌────────────┼────────────┐
                  │            │            │
                Apply       Applied      Rejected
                  │            │            │
               Paginated    Paginated    Paginated
```

| Concern | Endpoint | Behavior |
|---------|----------|----------|
| Counts | `GET /api/applications/counts` | One SQL aggregate; returns `{ apply, applied, rejected }` — **no job records** |
| Apply list | `GET /api/applications/queue?page=&page_size=` | Only Apply rows, hydrated for that page |
| Applied list | `GET /api/applications/applied?page=&page_size=` | Active applied only (excludes rejected) |
| Rejected list | `GET /api/applications/rejected?page=&page_size=` | Applied + rejected |

**Why separate:** Counting must not require fetching position records. Each state is an independent query — never one giant payload filtered in the browser.

**Pagination:** page / `page_size` (default **20**, max **20**). Response shape:

```json
{
  "jobs": [ /* board-shaped position cards */ ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 105,
    "total_pages": 6,
    "has_more": true
  }
}
```

SQL lives in [`positions/repo.py`](../../relocation_jobs/positions/repo.py) (`count_application_states`, `list_application_state_rows`). Hydration for the page only is in [`panel/application_queue.py`](../../relocation_jobs/panel/application_queue.py).

Opening Applications must **not** load all three lists. Preferred UX (Option A):

1. Fetch counts (lightweight).
2. Fetch the first page of the active tab (Apply by default).
3. Fetch Applied / Rejected only when those tabs are opened.

---

## Lifecycle

```text
Catalog position
       │
       ├─ Want to apply  → looking_to_apply=1
       └─ Pin            → pinned=1
              │
              ▼
     Apply tab  ←── panel /applications + MCP list_application_queue
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
     Applied tab  (active / awaiting response)
              │
              ▼
           Reject
              │
              ├─ rejected=1  (applied stays 1)
              │
              ▼
     Rejected tab
```

Pinning alone still puts a role in Apply until the user applies (or unpins with no looking-to-apply). Unpinning does **not** clear `looking_to_apply`. Applying does **not** require unpinning; applied rows are excluded from Apply even if still pinned.

Reject does **not** clear `applied`. Reapply clears rejection only and returns the row to Applied.

---

## Panel UI

| Surface | Role |
|---------|------|
| `/applications` | Tabs Apply / Applied / Rejected; reuses `<position-card>` |
| `GET /api/applications/counts` | Tab badges |
| `GET /api/applications/queue` | Paginated Apply |
| `GET /api/applications/applied` | Paginated active Applied |
| `GET /api/applications/rejected` | Paginated Rejected |
| Job Board | Company-centric; unchanged |

Client: [`static/js/applications.js`](../../relocation_jobs/static/js/applications.js) — per-tab loading, empty, error, and pagination state.

---

## MCP

| Tool | Filter |
|------|--------|
| `list_application_queue` | Apply predicate (full discovery list for assistants — not the paginated panel API) |
| `list_looking_to_apply_jobs` | `looking_to_apply` only (applied already clears that flag) |
| `get_job_context.in_application_queue` | Same Apply predicate |
| `mark_applied` | Calls `positions.service.set_job_applied` |

Tailoring does **not** require queue membership (`can_save_tailored_tex` stays true for catalog jobs).

---

## Invariants for future changes

1. Apply = outstanding to-apply work, never applied roles.
2. Applied excludes rejected; Rejected is its own state.
3. UI and MCP must read the same Apply predicate / DB state.
4. Apply from any surface (Applications, Job Board, MCP) must leave the Apply tab.
5. Do not hide applied rows only in the UI while leaving them in `list_application_queue`.
6. Reuse `<position-card>`; do not ship a parallel application-card design.
7. Never full-load all application states to render the Applications page or to compute counts.
