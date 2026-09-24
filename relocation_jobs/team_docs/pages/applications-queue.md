# Applications queue (panel + MCP)

## What it is

Each user has an **active application queue**: positions they pinned or marked Want to apply, that they have not applied to yet.

There is no separate queue table. Membership is on `job_tracking`:

`(pinned OR looking_to_apply) AND NOT applied`

## Where operators see it

- Panel left nav → **Applications** (`/applications`)
- Tabs: **To apply** (active queue) and **Applied** (application history)
- Each row reuses the same `<position-card>` as the Job Board and company workspace

## How positions enter

- Job Board / company workspace: **Want to apply** or **Pin**
- Public job save (`/jobs/<slug>/save`) sets looking-to-apply

## Apply

Marking Applied (panel or MCP `mark_applied`) sets `applied=1` and clears `looking_to_apply`. The role leaves the active queue even if it stays pinned for board sorting.

Apply from the Job Board or Applications page updates the same DB row; both UIs and MCP stay consistent.

## MCP / Claude / Cursor

`list_application_queue` returns only active-queue roles. After Apply, that role no longer appears as outstanding. Tailoring tools can still target a job by URL without queue membership.

## Ops notes

- No migration required for this feature; existing tracking rows are interpreted with the active-queue rule.
- Stale catalog roles with looking-to-apply or applied tracking are still listed (orphan hydrate) so operators do not lose tracked work.
- Duplicate queue rows cannot exist (one tracking row per user + job URL).

See engineering detail: `docs/reference/application-queue.md`.
