from __future__ import annotations

import json

from relocation_jobs.core.db import _utc_now, db_read, db_transaction
from relocation_jobs.credits.types import CreditBalance, CreditGrantKind


def _balance_rows(conn, user_id: int, now: str) -> tuple[int, int]:
    rows = conn.execute(
        """
        SELECT kind, COALESCE(SUM(remaining_credits), 0) AS credits
        FROM credit_grants
        WHERE user_id = %s AND remaining_credits > 0
          AND (expires_at IS NULL OR expires_at > %s)
        GROUP BY kind
        """,
        (user_id, now),
    ).fetchall()
    by_kind = {row["kind"]: int(row.get("credits") or 0) for row in rows}
    promotional = sum(
        credits
        for kind, credits in by_kind.items()
        if kind in (CreditGrantKind.MONTHLY.value, CreditGrantKind.SUBSCRIPTION.value)
    )
    purchased = sum(by_kind.values()) - promotional
    return promotional, purchased


def _lock_user(conn, user_id: int) -> None:
    conn.execute("UPDATE users SET id = id WHERE id = %s", (user_id,))


def create_grant(
    user_id: int,
    *,
    kind: CreditGrantKind,
    source_key: str,
    credits: int,
    expires_at: str | None,
    metadata: dict | None = None,
) -> bool:
    amount = max(0, int(credits))
    if amount <= 0:
        raise ValueError("Credit grant must be positive")
    now = _utc_now()
    with db_transaction() as conn:
        _lock_user(conn, user_id)
        existing = conn.execute(
            "SELECT id FROM credit_grants WHERE user_id = %s AND source_key = %s",
            (user_id, source_key),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO credit_grants (
                user_id, kind, source_key, total_credits, remaining_credits,
                expires_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, kind.value, source_key, amount, amount, expires_at, now),
        )
        promotional, purchased = _balance_rows(conn, user_id, now)
        conn.execute(
            """
            INSERT INTO credit_ledger (
                user_id, event_type, operation, amount, balance_after,
                idempotency_key, metadata_json, created_at
            ) VALUES (%s, 'grant', %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                kind.value,
                amount,
                promotional + purchased,
                f"grant:{source_key}",
                json.dumps(metadata or {}, sort_keys=True),
                now,
            ),
        )
    return True


def balance_totals(user_id: int) -> tuple[int, int]:
    now = _utc_now()
    with db_read() as conn:
        return _balance_rows(conn, user_id, now)


def expire_grants(user_id: int) -> int:
    now = _utc_now()
    expired_total = 0
    with db_transaction() as conn:
        _lock_user(conn, user_id)
        rows = conn.execute(
            """
            SELECT id, source_key, remaining_credits FROM credit_grants
            WHERE user_id = %s AND remaining_credits > 0
              AND expires_at IS NOT NULL AND expires_at <= %s
            ORDER BY expires_at ASC, id ASC
            """,
            (user_id, now),
        ).fetchall()
        for grant in rows:
            amount = int(grant["remaining_credits"])
            conn.execute(
                "UPDATE credit_grants SET remaining_credits = 0 WHERE id = %s",
                (grant["id"],),
            )
            promotional, purchased = _balance_rows(conn, user_id, now)
            conn.execute(
                """
                INSERT INTO credit_ledger (
                    user_id, event_type, operation, amount, balance_after,
                    idempotency_key, metadata_json, created_at
                ) VALUES (%s, 'expire', 'monthly_expiry', %s, %s, %s, '{}', %s)
                ON CONFLICT (user_id, idempotency_key) DO NOTHING
                """,
                (
                    user_id,
                    -amount,
                    promotional + purchased,
                    f"expire:{grant['source_key']}",
                    now,
                ),
            )
            expired_total += amount
    return expired_total


def spend_credits(
    user_id: int,
    *,
    cost: int,
    operation: str,
    idempotency_key: str,
    metadata: dict | None = None,
) -> dict:
    amount = max(1, int(cost))
    now = _utc_now()
    with db_transaction() as conn:
        _lock_user(conn, user_id)
        existing = conn.execute(
            """
            SELECT amount, balance_after FROM credit_ledger
            WHERE user_id = %s AND idempotency_key = %s
            """,
            (user_id, idempotency_key),
        ).fetchone()
        if existing:
            return {
                "spent": True,
                "deduplicated": True,
                "cost": abs(int(existing["amount"])),
                "balance": int(existing["balance_after"]),
            }
        grants = conn.execute(
            """
            SELECT id, kind, remaining_credits
            FROM credit_grants
            WHERE user_id = %s AND remaining_credits > 0
              AND (expires_at IS NULL OR expires_at > %s)
            ORDER BY CASE WHEN kind IN ('monthly', 'subscription') THEN 0 ELSE 1 END,
                     expires_at ASC, created_at ASC, id ASC
            """,
            (user_id, now),
        ).fetchall()
        available = sum(int(row["remaining_credits"]) for row in grants)
        if available < amount:
            return {
                "spent": False,
                "deduplicated": False,
                "cost": amount,
                "balance": available,
            }
        remaining = amount
        allocations = []
        for grant in grants:
            if remaining <= 0:
                break
            used = min(remaining, int(grant["remaining_credits"]))
            conn.execute(
                """
                UPDATE credit_grants
                SET remaining_credits = remaining_credits - %s
                WHERE id = %s
                """,
                (used, grant["id"]),
            )
            allocations.append({"grant_id": int(grant["id"]), "credits": used})
            remaining -= used
        balance_after = available - amount
        details = {**(metadata or {}), "allocations": allocations}
        conn.execute(
            """
            INSERT INTO credit_ledger (
                user_id, event_type, operation, amount, balance_after,
                idempotency_key, metadata_json, created_at
            ) VALUES (%s, 'spend', %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                operation,
                -amount,
                balance_after,
                idempotency_key,
                json.dumps(details, sort_keys=True),
                now,
            ),
        )
    return {
        "spent": True,
        "deduplicated": False,
        "cost": amount,
        "balance": balance_after,
    }


def refund_spend(user_id: int, *, spend_key: str, reason: str) -> bool:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT amount FROM credit_ledger
            WHERE user_id = %s AND idempotency_key = %s AND event_type = 'spend'
            """,
            (user_id, spend_key),
        ).fetchone()
    if not row:
        return False
    return create_grant(
        user_id,
        kind=CreditGrantKind.REFUND,
        source_key=f"refund:{spend_key}",
        credits=abs(int(row["amount"])),
        expires_at=None,
        metadata={"reason": reason, "spend_key": spend_key},
    )


def list_ledger(user_id: int, *, limit: int = 50) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT event_type, operation, amount, balance_after,
                   idempotency_key, metadata_json, created_at
            FROM credit_ledger
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (user_id, max(1, min(int(limit), 200))),
        ).fetchall()
    return [
        {
            **dict(row),
            "metadata": json.loads(row.get("metadata_json") or "{}"),
        }
        for row in rows
    ]


def usage_migration_done(user_id: int, period_key: str) -> bool:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT 1 AS ok FROM credit_usage_migrations
            WHERE user_id = %s AND period_key = %s
            """,
            (user_id, period_key),
        ).fetchone()
    return bool(row)


def mark_usage_migration_done(user_id: int, period_key: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO credit_usage_migrations (user_id, period_key, migrated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, period_key) DO NOTHING
            """,
            (user_id, period_key, _utc_now()),
        )


def create_order(
    user_id: int,
    *,
    pack_key: str,
    credits: int,
    price_minor: int,
    currency: str,
    provider: str,
    kind: str = "credits",
) -> int:
    now = _utc_now()
    order_kind = (kind or "credits").strip() or "credits"
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO credit_orders (
                user_id, pack_key, credits, price_minor, currency,
                provider, status, created_at, updated_at, kind
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                pack_key,
                credits,
                price_minor,
                currency,
                provider,
                now,
                now,
                order_kind,
            ),
        ).fetchone()
    return int(row["id"])


def update_order_checkout(
    order_id: int,
    *,
    provider_order_id: str,
    checkout_url: str,
) -> None:
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE credit_orders
            SET provider_order_id = %s, checkout_url = %s, updated_at = %s
            WHERE id = %s
            """,
            (provider_order_id, checkout_url, _utc_now(), order_id),
        )


def get_order(order_id: int, *, user_id: int | None = None) -> dict | None:
    params: tuple = (order_id,)
    where = "id = %s"
    if user_id is not None:
        where += " AND user_id = %s"
        params = (order_id, user_id)
    with db_read() as conn:
        row = conn.execute(f"SELECT * FROM credit_orders WHERE {where}", params).fetchone()
    return dict(row) if row else None


def get_order_by_provider(provider: str, provider_order_id: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT * FROM credit_orders
            WHERE provider = %s AND provider_order_id = %s
            """,
            (provider, provider_order_id),
        ).fetchone()
    return dict(row) if row else None


def list_orders(user_id: int, *, limit: int = 50) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT * FROM credit_orders WHERE user_id = %s
            ORDER BY created_at DESC, id DESC LIMIT %s
            """,
            (user_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [dict(row) for row in rows]


def record_payment_event(
    *,
    provider: str,
    event_id: str,
    provider_order_id: str,
    payload: dict,
) -> bool:
    with db_transaction() as conn:
        existing = conn.execute(
            "SELECT id FROM payment_events WHERE provider = %s AND event_id = %s",
            (provider, event_id),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO payment_events (
                provider, event_id, provider_order_id, payload_json, received_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                provider,
                event_id,
                provider_order_id,
                json.dumps(payload, sort_keys=True),
                _utc_now(),
            ),
        )
    return True


def mark_order_paid(provider: str, provider_order_id: str) -> dict | None:
    now = _utc_now()
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE credit_orders
            SET status = 'paid', paid_at = COALESCE(paid_at, %s), updated_at = %s
            WHERE provider = %s AND provider_order_id = %s
            """,
            (now, now, provider, provider_order_id),
        )
        row = conn.execute(
            """
            SELECT * FROM credit_orders
            WHERE provider = %s AND provider_order_id = %s
            """,
            (provider, provider_order_id),
        ).fetchone()
    return dict(row) if row else None


def update_order_status(provider: str, provider_order_id: str, status: str) -> dict | None:
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE credit_orders SET status = %s, updated_at = %s
            WHERE provider = %s AND provider_order_id = %s
            """,
            (status.strip().lower(), _utc_now(), provider, provider_order_id),
        )
        row = conn.execute(
            """
            SELECT * FROM credit_orders
            WHERE provider = %s AND provider_order_id = %s
            """,
            (provider, provider_order_id),
        ).fetchone()
    return dict(row) if row else None


def list_orders_for_admin(*, limit: int = 100) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT * FROM credit_orders
            ORDER BY created_at DESC, id DESC LIMIT %s
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def revoke_order_grant(order: dict, *, reason: str) -> int:
    source_key = f"order:{order['provider']}:{order['provider_order_id']}"
    idempotency_key = f"revoke:{source_key}"
    now = _utc_now()
    with db_transaction() as conn:
        _lock_user(conn, int(order["user_id"]))
        existing = conn.execute(
            """
            SELECT id FROM credit_ledger
            WHERE user_id = %s AND idempotency_key = %s
            """,
            (order["user_id"], idempotency_key),
        ).fetchone()
        if existing:
            return 0
        grant = conn.execute(
            """
            SELECT id, remaining_credits FROM credit_grants
            WHERE user_id = %s AND source_key = %s
            """,
            (order["user_id"], source_key),
        ).fetchone()
        if not grant:
            return 0
        revoked = int(grant["remaining_credits"])
        conn.execute(
            "UPDATE credit_grants SET remaining_credits = 0 WHERE id = %s",
            (grant["id"],),
        )
        promotional, purchased = _balance_rows(conn, int(order["user_id"]), now)
        conn.execute(
            """
            INSERT INTO credit_ledger (
                user_id, event_type, operation, amount, balance_after,
                idempotency_key, metadata_json, created_at
            ) VALUES (%s, 'revoke', 'order_refund', %s, %s, %s, %s, %s)
            """,
            (
                order["user_id"],
                -revoked,
                promotional + purchased,
                idempotency_key,
                json.dumps({"order_id": order["id"], "reason": reason}, sort_keys=True),
                now,
            ),
        )
    return revoked


def credit_audit() -> dict:
    now = _utc_now()
    with db_read() as conn:
        negative = conn.execute(
            """
            SELECT COUNT(*) AS n FROM credit_grants
            WHERE remaining_credits < 0 OR remaining_credits > total_credits
            """
        ).fetchone()
        paid_orders = conn.execute(
            "SELECT * FROM credit_orders WHERE status = 'paid'",
        ).fetchall()
        users = conn.execute(
            "SELECT DISTINCT user_id FROM credit_grants",
        ).fetchall()
        missing_grants = []
        for order in paid_orders:
            if str(order.get("kind") or "credits") == "full_access":
                continue
            source_key = f"order:{order['provider']}:{order['provider_order_id']}"
            grant = conn.execute(
                """
                SELECT id FROM credit_grants
                WHERE user_id = %s AND source_key = %s
                """,
                (order["user_id"], source_key),
            ).fetchone()
            if not grant:
                missing_grants.append(int(order["id"]))
        mismatches = []
        for user in users:
            promotional, purchased = _balance_rows(conn, int(user["user_id"]), now)
            latest = conn.execute(
                """
                SELECT balance_after FROM credit_ledger
                WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (user["user_id"],),
            ).fetchone()
            if latest and int(latest["balance_after"]) != promotional + purchased:
                mismatches.append(int(user["user_id"]))
    return {
        "ok": (
            int((negative or {}).get("n") or 0) == 0
            and not missing_grants
            and not mismatches
        ),
        "invalid_grant_balances": int((negative or {}).get("n") or 0),
        "paid_orders_without_grants": missing_grants,
        "ledger_balance_mismatches": mismatches,
    }
