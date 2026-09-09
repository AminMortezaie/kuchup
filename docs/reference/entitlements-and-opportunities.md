# Entitlements and personalized opportunities

**Status:** Phase A–F implemented; G planned  
**Related plan:** Cursor plan `google-only_auth` (personalized opportunities via Google identity + plans)

## Identity (Phase A — shipped)

- Google OAuth is the only sign-in tunnel (panel + MCP).
- Env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, optional `GOOGLE_REDIRECT_URI`.
- Admins: `PANEL_ADMIN_EMAILS` (comma-separated).
- Self-serve signup: `PANEL_ALLOW_REGISTER=1`.
- Routes: `GET /api/auth/google`, `GET /api/auth/google/callback`, `GET /api/auth/status`, `POST /api/auth/logout`.
- Production panel deploy sets `SESSION_COOKIE_SECURE=1`.

## Plans (Phase B + freemium capacity)

| Plan | Board | Positions | MCP daily |
|------|-------|-----------|-----------|
| `free` | Sticky company slots via `FREE_BOARD_COMPANY_CAP` (default **10**), open-role only | 3 stable active roles/company; 30 promotional credits/calendar month; optional top-ups | `FREE_MCP_DAILY_REQUESTS` (default 20) |
| `full` / `grandfathered` | Prefs-scoped, no company cap | All roles | `FULL_MCP_DAILY_REQUESTS` (default 500; `0` = unlimited) |
| Admin | Bypass opportunity filter | Bypass | Bypass |

### Module map

| Domain | Role |
|--------|------|
| [`core/sqs_client.py`](../../relocation_jobs/core/sqs_client.py) | SQS transport only |
| [`async_jobs/`](../../relocation_jobs/async_jobs/) | Typed SQS enqueue only (no Python consumer) |
| [`opportunities/`](../../relocation_jobs/opportunities/) | Preference + opportunity **reads**; enqueue refresh. Runtime sticky: Go `ReconcileSticky`. Python `reconcile.py` is test-only. |
| [`broadcast/`](../../relocation_jobs/broadcast/) | Freemium peek / consume / capacity meta. Replacement **writes**: Go via `type=replace` |
| [`credits/`](../../relocation_jobs/credits/) | Monthly/purchased grants, wallet balance, immutable ledger, atomic spend/refund |
| [`payments/`](../../relocation_jobs/payments/) | Provider-neutral checkout orchestration + NOWPayments adapter |

Rematch **keeps** sticky slots; fills vacant slots with newest open-role companies only (no empty careers shells).

Free position capacity is assignment-based:

- Initial role assignments do not consume the monthly allowance.
- Merely rendering a role or opening its external job link does not consume it.
- Seen, Interested, Applied, Rejected, Not for me, Referral, Reapply, and Pin
  remain free. When one of these actions can deliver a new replacement role,
  that successful delivery consumes one credit.
- Repeating actions on the same role is deduplicated and never double-charged.
- Free users receive 30 expiring promotional credits each UTC month.
  Purchased credits are used after promotional credits and never expire.
- If no replacement exists or assignment fails, no credit is spent.
- Previously assigned roles remain visible if a later scrape removes them;
  they are labelled as absent from the latest fetch instead of disappearing.

- Admin grant: `PATCH /api/admin/users/<id>/plan`
- `GET /api/auth/status` includes `entitlements` (`plan`, `board_company_cap`, `jobs_per_company`, `total_position_budget`, `mcp_daily_*`, `public_job_saves_used`, `public_job_saves_remaining`)
- MCP write/render tools call `consume_mcp_quota` ([`users/entitlements.py`](../../relocation_jobs/users/entitlements.py)).

## Public job-page saves (LinkedIn wrapping funnel)

Visa job pages at `GET /jobs/<slug>` are the LinkedIn/Google on-ramp. The primary CTA saves the role into looking-to-apply. The employer ATS URL is only shown in the company workspace after the role is tracked. `/jobs/<slug>/employer` is a compatibility redirect into `/save` (same 3/day + credit wall).

| Plan | Unique `/jobs/<slug>/save` |
|------|----------------------------|
| `free` | First **3** unique jobs per UTC day are free (`FREE_PUBLIC_JOB_SAVES_PER_DAY`). Further unique saves spend **1** credit (`PUBLIC_JOB_SAVE`). Empty wallet stays on the job page with a pack / Full Access CTA. |
| `full` / `grandfathered` / admin | Unlimited; no credit spend |

- Re-saving a job already in looking-to-apply, or already recorded on the public-save ledger, does not count again.
- Board/API `looking_to_apply` stays free and does not increment the public-save counter.
- Credits are the existing wallet (30 monthly promo, then purchased packs). Board replacement-credit rules are unchanged.

## Personalized board reads (Phase D — shipped)

- Authenticated **non-admin** board reads (`GET /api/board`) filter companies to `user_opportunities`, then [`broadcast`](../../relocation_jobs/broadcast/) truncates jobs for free users.
- Company workspace (`GET /api/mcp/companies/<country>/<company>/applications`) uses the same assignment cap. Looking-to-apply, applied, pinned, and rejected roles stay visible even if they sit outside the current 3. `GET /api/jobs` and `GET /api/companies/<country>/<name>` apply the same filter.
- Meta includes capacity: `company_slots_used/cap`, `positions_used/budget`, `jobs_per_company_peek`, `upgrade_reason`.
- **Remote board** does **not** apply relocation opportunity keys.
- **Default preferences:** `germany` until confirmed.
- Free at slot/budget wall → upgrade CTAs on board strip and company cards.

Preferences API + onboarding UI (Phase C): unchanged (`GET`/`PUT /api/preferences`).

## Credit checkout and Full Access (Phase F — shipped)

Credit packs are 10/$0.99, 50/$4.99, 150/$11.99, and 400/$24.99. Full Access is **$29
one-time** and sets `plan=full`. Checkout uses NOWPayments invoice creation
plus signed IPN callbacks. Credits and plan changes apply only from a verified
paid event (`confirmed` / `finished`); browser redirects never mutate a wallet
or plan. Refunds revoke unused purchased credits and return Full Access to
`free` unless the account is admin or `grandfathered`.

Ops: [`docs/operations/nowpayments.md`](../operations/nowpayments.md).

## Next

- **G** Infra SQS (fetch/PDF) per [multi-user-scaling-proposal.md](multi-user-scaling-proposal.md)

## Opportunity refresh (Phase E — shipped)

- Tables: `user_preferences`, `user_opportunities` (sticky company keys),
  `position_broadcast_assignments` (stable monthly job assignments),
  `credit_grants`, `credit_ledger`, `credit_orders`, and `payment_events`
- Domains: [`opportunities/`](../../relocation_jobs/opportunities/), [`broadcast/`](../../relocation_jobs/broadcast/), [`async_jobs/`](../../relocation_jobs/async_jobs/)
- SQS: `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` + [`apps/role-propagator/`](../../apps/role-propagator/) (Go, sole assignment writer)
- When SQS unset: `ROLE_PROPAGATOR_BIN` runs the Go one-shot; if both are unset, enqueue raises
- Producers: login, prefs save, fetch run finish (`fetch/runner.py`), admin plan, payments, role replacement, `build_companies`. Not board GET.
- Caps live in [`users/entitlements.py`](../../relocation_jobs/users/entitlements.py); Go reads the same env vars (`FREE_BOARD_COMPANY_CAP`, …).
