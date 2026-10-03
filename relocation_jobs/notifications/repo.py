from __future__ import annotations

from relocation_jobs.core.db import _utc_now, db_read, db_transaction


def upsert_subscription(
    user_id: int,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
) -> None:
    endpoint = (endpoint or "").strip()
    p256dh = (p256dh or "").strip()
    auth = (auth or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError("Incomplete push subscription")
    now = _utc_now()
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO web_push_subscriptions (
                user_id, endpoint, p256dh, auth, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth,
                updated_at = EXCLUDED.updated_at
            """,
            (int(user_id), endpoint, p256dh, auth, now, now),
        )


def delete_subscription(user_id: int, *, endpoint: str) -> bool:
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return False
    with db_transaction() as conn:
        cur = conn.execute(
            """
            DELETE FROM web_push_subscriptions
            WHERE user_id = %s AND endpoint = %s
            """,
            (int(user_id), endpoint),
        )
        return int(cur.rowcount or 0) > 0


def delete_subscription_by_endpoint(endpoint: str) -> None:
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return
    with db_transaction() as conn:
        conn.execute(
            "DELETE FROM web_push_subscriptions WHERE endpoint = %s",
            (endpoint,),
        )


def list_subscriptions_for_user(user_id: int) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, endpoint, p256dh, auth, created_at, updated_at
            FROM web_push_subscriptions
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (int(user_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def record_wave_jobs(
    fetch_run_id: int,
    country: str,
    company_name: str,
    job_keys: list[str],
) -> None:
    run_id = int(fetch_run_id)
    if run_id <= 0 or not job_keys:
        return
    country_key = (country or "").strip().lower()
    company = (company_name or "").strip()
    if not country_key or not company:
        return
    now = _utc_now()
    keys = sorted({(k or "").strip() for k in job_keys if (k or "").strip()})
    if not keys:
        return
    with db_transaction() as conn:
        for key in keys:
            conn.execute(
                """
                INSERT INTO fetch_wave_new_jobs (
                    fetch_run_id, country, company_name, job_key, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (fetch_run_id, country, company_name, job_key) DO NOTHING
                """,
                (run_id, country_key, company, key, now),
            )


def count_wave_jobs_for_user(user_id: int, fetch_run_id: int) -> int:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT w.job_key) AS n
            FROM fetch_wave_new_jobs w
            INNER JOIN user_opportunities uo
              ON uo.user_id = %s
             AND uo.country = w.country
             AND lower(uo.company_name) = lower(w.company_name)
            WHERE w.fetch_run_id = %s
            """,
            (int(user_id), int(fetch_run_id)),
        ).fetchone()
    return int((row or {}).get("n") or 0)


def push_wave_already_sent(user_id: int, fetch_run_id: int) -> bool:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM fetch_wave_push_sent
            WHERE user_id = %s AND fetch_run_id = %s
            """,
            (int(user_id), int(fetch_run_id)),
        ).fetchone()
    return row is not None


def claim_push_sent(user_id: int, fetch_run_id: int) -> bool:
    now = _utc_now()
    with db_transaction() as conn:
        existing = conn.execute(
            """
            SELECT 1 FROM fetch_wave_push_sent
            WHERE user_id = %s AND fetch_run_id = %s
            """,
            (int(user_id), int(fetch_run_id)),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO fetch_wave_push_sent (user_id, fetch_run_id, sent_at)
            VALUES (%s, %s, %s)
            """,
            (int(user_id), int(fetch_run_id), now),
        )
    return True


def list_full_plan_subscribed_user_ids() -> list[int]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.id AS id
            FROM users u
            INNER JOIN web_push_subscriptions s ON s.user_id = u.id
            WHERE lower(COALESCE(u.plan, 'free')) IN ('full', 'grandfathered')
            ORDER BY u.id ASC
            """
        ).fetchall()
    return [int(row["id"]) for row in rows]
