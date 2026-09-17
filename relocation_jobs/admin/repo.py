from __future__ import annotations

from relocation_jobs.core.db import db_read


def _count(sql: str, params: tuple = ()) -> int:
    with db_read() as conn:
        row = conn.execute(sql, params).fetchone()
    return int((row or {}).get("n") or 0)


def _one(sql: str, params: tuple = ()) -> dict | None:
    with db_read() as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    return dict(row)


def _many(sql: str, params: tuple = ()) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def list_users_for_activation() -> list[dict]:
    return _many(
        """
        SELECT id, username, plan, created_at, mcp_quota_used, mcp_quota_date
        FROM users
        ORDER BY created_at ASC, id ASC
        """
    )


def count_users_with_job_track() -> int:
    return _count(
        """
        SELECT COUNT(*) AS n FROM users u
        WHERE EXISTS (SELECT 1 FROM job_tracking t WHERE t.user_id = u.id)
        """
    )


def count_users_with_workspace() -> int:
    return _count(
        """
        SELECT COUNT(*) AS n FROM users u
        WHERE EXISTS (SELECT 1 FROM mcp_applications a WHERE a.user_id = u.id)
        """
    )


def count_users_with_mcp() -> int:
    return _count(
        """
        SELECT COUNT(*) AS n FROM users u
        WHERE COALESCE(u.mcp_quota_used, 0) > 0
           OR EXISTS (SELECT 1 FROM mcp_oauth_tokens t WHERE t.user_id = u.id)
           OR EXISTS (SELECT 1 FROM mcp_api_tokens t WHERE t.user_id = u.id)
        """
    )


def count_users_with_paid_order(kind: str) -> int:
    return _count(
        """
        SELECT COUNT(*) AS n FROM users u
        WHERE EXISTS (
            SELECT 1 FROM credit_orders o
            WHERE o.user_id = u.id
              AND o.status = 'paid'
              AND o.kind = %s
        )
        """,
        (kind,),
    )


def count_users_with_subsequent_login() -> int:
    return _count(
        """
        SELECT COUNT(*) AS n FROM users
        WHERE last_login_at IS NOT NULL
          AND TRIM(last_login_at) <> ''
          AND last_login_at > created_at
        """
    )


def latest_signup() -> dict | None:
    return _one(
        """
        SELECT id AS user_id, username, created_at AS at
        FROM users
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    )


def latest_subsequent_login() -> dict | None:
    return _one(
        """
        SELECT id AS user_id, username, last_login_at AS at
        FROM users
        WHERE last_login_at IS NOT NULL
          AND TRIM(last_login_at) <> ''
          AND last_login_at > created_at
        ORDER BY last_login_at DESC, id DESC
        LIMIT 1
        """
    )


def latest_job_track() -> dict | None:
    return _one(
        """
        SELECT u.id AS user_id, u.username, t.updated_at AS at
        FROM job_tracking t
        JOIN users u ON u.id = t.user_id
        ORDER BY t.updated_at DESC
        LIMIT 1
        """
    )


def latest_workspace() -> dict | None:
    return _one(
        """
        SELECT u.id AS user_id, u.username, a.updated_at AS at
        FROM mcp_applications a
        JOIN users u ON u.id = a.user_id
        ORDER BY a.updated_at DESC
        LIMIT 1
        """
    )


def mcp_activity_rows() -> list[dict]:
    return _many(
        """
        SELECT u.id AS user_id, u.username, src.at, src.signal
        FROM (
            SELECT user_id, created_at AS at, 'oauth_token' AS signal
            FROM mcp_oauth_tokens
            UNION ALL
            SELECT user_id, COALESCE(last_used_at, created_at) AS at, 'api_token' AS signal
            FROM mcp_api_tokens
            UNION ALL
            SELECT id AS user_id, mcp_quota_date AS at, 'quota' AS signal
            FROM users
            WHERE COALESCE(mcp_quota_used, 0) > 0
              AND mcp_quota_date IS NOT NULL
              AND TRIM(mcp_quota_date) <> ''
        ) src
        JOIN users u ON u.id = src.user_id
        WHERE src.at IS NOT NULL AND TRIM(src.at) <> ''
        """
    )


def latest_paid_order(kind: str) -> dict | None:
    return _one(
        """
        SELECT u.id AS user_id, u.username, o.paid_at AS at, o.kind
        FROM credit_orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.status = 'paid'
          AND o.kind = %s
          AND o.paid_at IS NOT NULL
          AND TRIM(o.paid_at) <> ''
        ORDER BY o.paid_at DESC, o.id DESC
        LIMIT 1
        """,
        (kind,),
    )
