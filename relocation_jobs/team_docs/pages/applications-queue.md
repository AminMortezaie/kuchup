# Applications queue (panel + MCP)

## What it is

Each user has three **application states** derived from `job_tracking` (no separate queue table):

| Tab | Meaning | Rule |
|-----|---------|------|
| **Apply** | Still needs application | `(pinned OR looking_to_apply) AND NOT applied AND NOT rejected AND NOT not_for_me` |
| **Applied** | Submitted, awaiting response | `applied AND NOT rejected AND NOT not_for_me` |
| **Rejected** | Marked rejected | `rejected AND NOT not_for_me` |

## Where operators see it

- Panel left nav → **Applications** (`/applications`)
- Tabs: **Apply**, **Applied**, **Rejected** (counts from `GET /api/applications/counts`)
- Each row reuses the same `<position-card>` as the Job Board and company workspace
- Lists are **paginated** (20 per page); opening Applications does not load all three datasets

## Data loading

1. Counts API (lightweight aggregates) — no position records
2. Only the active tab’s first page of positions
3. Other tabs load on click; pagination stays per-tab

## How positions enter Apply

- Job Board / company workspace: **Want to apply** or **Pin**
- Public job save (`/jobs/<slug>/save`) sets looking-to-apply

## Transitions

- **Apply → Applied:** Mark Applied (panel or MCP `mark_applied`) sets `applied=1` and clears `looking_to_apply`
- **Any tab → out of Applications:** Not for me (any reason: not for me, expired, wrong location, no relocation) sets `not_for_me=1` and drops the role from Apply, Applied, and Rejected. The card keeps the reason tag (Expired, Wrong location, and so on). Restore puts it back only if it still matches a state rule.
- **Any tab → Rejected:** Reject sets `rejected=1`. The role leaves Apply even when it was never marked applied. Reapply clears rejection only.

## MCP / Claude / Cursor

`list_application_queue` returns Apply-state roles for discovery (full list for assistants). After Apply, that role no longer appears as outstanding. Tailoring tools can still target a job by URL without queue membership.

## Ops notes

- No migration required; states are interpreted from existing `job_tracking` flags.
- Stale catalog roles with looking-to-apply or applied tracking are still listed (orphan hydrate).
- Duplicate rows cannot exist (one tracking row per user + job URL).
- Count and list SQL filter at the database; do not hydrate full histories just to show tab badges.

See engineering detail: `docs/reference/application-queue.md`.
