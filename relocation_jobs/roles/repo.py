from __future__ import annotations

from relocation_jobs.core.db import db_read, db_transaction


def list_role_filter_tags() -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, keyword, kind, is_default
            FROM role_filter_tags
            ORDER BY kind, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def find_role_filter_tag(kind: str, keyword: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, keyword, kind, is_default
            FROM role_filter_tags
            WHERE kind = %s AND keyword = %s
            """,
            (kind, keyword),
        ).fetchone()
    return dict(row) if row else None


def get_role_filter_tag(tag_id: int) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, keyword, kind, is_default
            FROM role_filter_tags
            WHERE id = %s
            """,
            (tag_id,),
        ).fetchone()
    return dict(row) if row else None


def insert_role_filter_tag(keyword: str, kind: str) -> dict:
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO role_filter_tags (keyword, kind, is_default)
            VALUES (%s, %s, 1)
            RETURNING id, keyword, kind, is_default
            """,
            (keyword, kind),
        ).fetchone()
    return dict(row)


def update_role_filter_tag(tag_id: int, keyword: str, kind: str) -> dict | None:
    with db_transaction() as conn:
        row = conn.execute(
            """
            UPDATE role_filter_tags
            SET keyword = %s, kind = %s
            WHERE id = %s
            RETURNING id, keyword, kind, is_default
            """,
            (keyword, kind, tag_id),
        ).fetchone()
    return dict(row) if row else None


def list_disabled_tag_ids(user_id: int) -> list[int]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT tag_id
            FROM user_role_tag_prefs
            WHERE user_id = %s AND enabled = 0
            """,
            (user_id,),
        ).fetchall()
    return [int(row["tag_id"]) for row in rows]


def delete_user_tag_pref(user_id: int, tag_id: int) -> None:
    with db_transaction() as conn:
        conn.execute(
            """
            DELETE FROM user_role_tag_prefs
            WHERE user_id = %s AND tag_id = %s
            """,
            (user_id, tag_id),
        )


def upsert_disabled_tag_pref(user_id: int, tag_id: int) -> None:
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_role_tag_prefs (user_id, tag_id, enabled)
            VALUES (%s, %s, 0)
            ON CONFLICT (user_id, tag_id) DO UPDATE SET enabled = 0
            """,
            (user_id, tag_id),
        )


def list_open_nondefault_jobs(company_keys: list[tuple[str, str]]) -> list[dict]:
    keys = [
        ((country or "").strip().lower(), (name or "").strip())
        for country, name in company_keys
        if (country or "").strip() and (name or "").strip()
    ]
    if not keys:
        return []
    clauses = " OR ".join(
        ["(c.country = %s AND lower(c.name) = lower(%s))"] * len(keys)
    )
    params = tuple(value for pair in keys for value in pair)
    with db_read() as conn:
        rows = conn.execute(
            f"""
            SELECT c.country, c.name AS company_name,
                   j.title, j.url, j.idempotency_key, j.fetched, j.last_seen,
                   j.location, j.locations_json, j.closed_at
            FROM companies c
            JOIN matching_jobs j ON j.company_id = c.id
            WHERE ({clauses})
              AND COALESCE(j.matches_default_filter, 1) = 0
              AND (j.closed_at IS NULL OR j.closed_at = '')
            ORDER BY c.country, c.name, j.title
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]
