# Panel statistics

**Last updated:** 2026-09-17

How admin/user stats are computed. Implementation: `panel/stats.py`, `relocation_jobs/static/js/stats-dashboard.js`.

> Stats are not yet a dedicated domain module — they are derived at read time from flattened catalog + tracking + `fetch_runs`. A future `stats/` package should own these queries.

---

## Admin home (`GET /api/admin/dashboard`)

Home pane only: worker status and `user_count`. Other panes hit their own routes:

| Pane | Route |
|------|-------|
| Home | `GET /api/admin/dashboard` then async `GET /api/admin/panel-stats` |
| Catalog / Fetch problems | `GET /api/admin/catalog` |
| Users | `GET /api/admin/users` (+ credit-orders / credits/audit) |
| Activation | `GET /api/admin/activation-metrics` |
| New jobs | `GET /api/admin/recent-jobs` |
| Fetch runs | `GET /api/admin/fetch-runs` |
| Config | `GET /api/admin/config` |

`panel_stats` is `null` on the home payload — load via `GET /api/admin/panel-stats`.

### Activation (`GET /api/admin/activation-metrics`)

Read-time funnel for Amin. SQL lives in `admin/repo.py`; the pane is `static/js/admin.js` `#activation`. No new tables and no extra roles.

| Metric | Source | Real? |
|--------|--------|-------|
| **Total users** | `users` row count | Yes |
| **Signups this week / weekly cohorts** | `users.created_at` grouped by ISO week (Monday UTC) | Yes |
| **free / full / grandfathered** | `users.plan` (`relocation_jobs/users/entitlements.py`) | Yes |
| **Job track** | Distinct users with a `job_tracking` row | Yes |
| **Workspace** | Distinct users with an `mcp_applications` row | Yes — artifacts only; page views of `/company/…` are not stored |
| **MCP** | `users.mcp_quota_used > 0` or an MCP OAuth/API token | Yes — read-only MCP with no quota/token is not stored |
| **Credit purchase** | Distinct users with a **paid** `credit_orders` row, `kind=credits` | Yes |
| **Full purchase** | Distinct users with a **paid** `credit_orders` row, `kind=full_access` | Yes |
| **Subsequent login** | — | **Gap.** No `last_login` / login-events table; Flask sessions are cookie-only |
| **Latest activity** | Newest timestamp per stored signal above | Yes where the signal exists; subsequent login shows the gap |

Admin plan grants are not purchases. Pending checkout orders are not counted.

### Your pipeline (`panel_stats`)

Per-user totals over the **full catalog** (not the current board page). Uses `flatten_companies_for_stats()` + `compute_stats()`.

| Stat | Meaning |
|------|---------|
| **Open roles** | Main-board jobs you can still act on: in the `jobs` bucket, **not applied**, **not not-for-me**. Excludes rejected roles. |
| **Co. with open roles** | Companies with at least one open role. |
| **New today** | Sum of `fetch_runs.new_jobs` for your account finished **today** (browser timezone). True new discoveries only — not jobs re-enriched on an existing fetch. |
| **Not for me** | Roles in the `not_for_me_jobs` bucket (user-hidden, wrong location, expired, etc.). Never included in open roles. |

**Job dates:** `fetched` = first time the job entered the catalog; `last_seen` = last ATS scrape. Post-fetch visa enrich must **never** overwrite `fetched` (see `scrape/enrich.py`).
| **Last fetch** | Latest company activity timestamp in scope. |
| **Applied today / total** | From `job_tracking` + status history. |
| **Rejections** | Jobs in the `rejected_jobs` bucket. |
| **Visa / relocation** | Open roles with `visa_sponsorship=true`. |

**Catalog table:** **Stored roles** = raw `matching_jobs` count (all users, no tracking overlay). Use **Your pipeline** for actionable numbers.

---

## Board header chip

`GET /api/board` returns lightweight `user_stats`; `latest_fetch_new_jobs` uses the same **New today** logic via `fetch_runs`.

---

## Legacy field

`country_meta.last_fetch_new_jobs` is updated only on country-wide fetch completion. **Do not use** for UI stats — kept for catalog metadata only.
