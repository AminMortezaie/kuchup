# NOWPayments checkout (kuchup.com)

**Provider:** NOWPayments invoices + signed IPN  
**Panel callback:** `https://kuchup.com/api/payments/nowpayments/ipn`  
**Secrets:** gitignored `.env` only — never commit API keys or IPN secrets

Checkout sells credit packs (10/$0.99, 50/$4.99, 150/$11.99, 400/$24.99) and one-time **Full Access ($29)**. Credits and plan changes apply only after a verified paid IPN (`confirmed` or `finished`). Browser `success_url` / `cancel_url` redirects never mutate a wallet or plan.

---

## Environment

| Variable | Role |
|----------|------|
| `NOWPAYMENTS_API_KEY` | Invoice API key from the NOWPayments dashboard |
| `NOWPAYMENTS_IPN_SECRET` | HMAC-SHA512 secret for IPN signatures |
| `NOWPAYMENTS_SANDBOX` | `1` uses `https://api-sandbox.nowpayments.io`; unset in production |
| `PANEL_PUBLIC_BASE_URL` | Must be `https://kuchup.com` so invoice callbacks are not `http://127.0.0.1` |

`./scripts/ec2_app_deploy.sh deploy` copies these from local `.env` onto the panel container.

---

## Dashboard

1. Generate an IPN secret under Payment Settings and save it as `NOWPAYMENTS_IPN_SECRET`.
2. Create an API key and save it as `NOWPAYMENTS_API_KEY`.
3. Set the dashboard **IPN callback url** to `https://kuchup.com/api/payments/nowpayments/ipn` (GET returns `{"ok": true}`; signed POSTs grant credits / Full Access).
4. Invoice create also sends that same `ipn_callback_url` on every checkout.
5. Sandbox first: set `NOWPAYMENTS_SANDBOX=1` locally, pay a test invoice, confirm the panel log line `payment_event paid=True`.
6. Production: unset sandbox, put live keys in `.env`, deploy.

If the origin security group is Cloudflare-only, keep the orange cloud on `kuchup.com` so NOWPayments can reach IPN through Cloudflare.

---

## Smoke

1. Sign in as a Free Google user.
2. Open Credits → starter pack or Unlock Full Access.
3. Complete sandbox payment.
4. Confirm wallet credits or `plan=full` on `GET /api/auth/status`.
5. Loki: `{job="docker"} |= "checkout_started"` or `payment_event`.
6. Admin: `GET /api/admin/credits/audit` should stay healthy. Reconcile with `POST /api/admin/credit-orders/<id>/reconcile` if a paid order missed a grant.

Refunds via the provider set the order to `refunded`, revoke unused purchased credits, and return Full Access to `free` unless the user is admin or `grandfathered`.
