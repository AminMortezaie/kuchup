# Entitlements and personalized opportunities

**Status:** Phase A–B–C–D–E implemented; F–G planned  
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
| [`async_jobs/`](../../relocation_jobs/async_jobs/) | Typed enqueue/dispatch (reconcile user/country) |
| [`opportunities/`](../../relocation_jobs/opportunities/) | Sticky company matching / reconcile |
| [`broadcast/`](../../relocation_jobs/broadcast/) | Freemium position broadcast (truncate, reveal-on-touch, capacity meta) |
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
- `GET /api/auth/status` includes `entitlements` (`plan`, `board_company_cap`, `jobs_per_company`, `total_position_budget`, `mcp_daily_*`)
- MCP write/render tools call `consume_mcp_quota` ([`users/entitlements.py`](../../relocation_jobs/users/entitlements.py)).

## Personalized board reads (Phase D — shipped)

- Authenticated **non-admin** board reads (`GET /api/board`) filter companies to `user_opportunities`, then [`broadcast`](../../relocation_jobs/broadcast/) truncates jobs for free users.
- Meta includes capacity: `company_slots_used/cap`, `positions_used/budget`, `jobs_per_company_peek`, `upgrade_reason`.
- **Remote board** does **not** apply relocation opportunity keys.
- **Default preferences:** `germany` until confirmed.
- Free at slot/budget wall → upgrade CTAs on board strip and company cards.

Preferences API + onboarding UI (Phase C): unchanged (`GET`/`PUT /api/preferences`).

## Credit checkout

Credit packs are 50/$4.99, 150/$11.99, and 400/$24.99. Checkout uses
NOWPayments invoice creation plus signed IPN callbacks. Credits are granted only
from a verified paid event; browser redirects never mutate a wallet. Full Access
remains a separate plan capability.

## Next

- **G** Infra SQS (fetch/PDF) per [multi-user-scaling-proposal.md](multi-user-scaling-proposal.md)
- Opportunity SQS worker deploy + DLQ alarms when enabling `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL`

## Opportunity refresh (Phase E — shipped)

- Tables: `user_preferences`, `user_opportunities` (sticky company keys),
  `position_broadcast_assignments` (stable monthly job assignments),
  `credit_grants`, `credit_ledger`, `credit_orders`, and `payment_events`
- Domains: [`opportunities/`](../../relocation_jobs/opportunities/), [`broadcast/`](../../relocation_jobs/broadcast/), [`async_jobs/`](../../relocation_jobs/async_jobs/)
- SQS: `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` + [`scripts/opportunity_sqs_worker.py`](../../scripts/opportunity_sqs_worker.py) → `async_jobs.dispatch.poll_once`
- When SQS unset: refresh runs inline (sync)
- Producers: fetch country end, company persist, prefs save, admin plan, `build_companies`
