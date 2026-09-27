from __future__ import annotations

import os

import pytest

from relocation_jobs.core.migrations import _ensure_users_email_confirmed_at, _ensure_users_password_hash


@pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", "").lower(),
    reason="requires PostgreSQL (psycopg placeholder rules)",
)
def test_email_confirmed_at_migration_on_postgres():
    from relocation_jobs.core.db import close_connection_pool, db_transaction, reset_db_initialized
    from relocation_jobs.db import init_db

    close_connection_pool()
    reset_db_initialized()
    init_db()
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (username, google_sub, email, created_at)
            VALUES ('oauth-user', 'google-sub-1', 'oauth@example.com', '2026-01-01T00:00:00+00:00')
            ON CONFLICT DO NOTHING
            """
        )
        _ensure_users_password_hash(conn)
        _ensure_users_email_confirmed_at(conn)
        row = conn.execute(
            "SELECT email_confirmed_at FROM users WHERE email = %s",
            ("oauth@example.com",),
        ).fetchone()
    assert row is not None
    assert (row.get("email_confirmed_at") or "").strip()
