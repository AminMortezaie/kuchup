from __future__ import annotations

from relocation_jobs.catalog.repo import _job_row
from relocation_jobs.core.db import db_read, db_transaction


def list_role_filter_tags() -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, keyword, kind
            FROM role_filter_tags
            ORDER BY kind, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def find_role_filter_tag(kind: str, keyword: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, keyword, kind
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
            SELECT id, keyword, kind
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
            INSERT INTO role_filter_tags (keyword, kind)
            VALUES (%s, %s)
            RETURNING id, keyword, kind
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
            RETURNING id, keyword, kind
            """,
            (keyword, kind, tag_id),
        ).fetchone()
    return dict(row) if row else None


def delete_role_filter_tag(tag_id: int) -> bool:
    with db_transaction() as conn:
        row = conn.execute(
            "DELETE FROM role_filter_tags WHERE id = %s RETURNING id",
            (tag_id,),
        ).fetchone()
    return row is not None


def list_disabled_tag_ids(user_id: int) -> list[int]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT tag_id
            FROM user_role_tag_prefs
            WHERE user_id = %s
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
            INSERT INTO user_role_tag_prefs (user_id, tag_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, tag_id) DO NOTHING
            """,
            (user_id, tag_id),
        )


def list_user_role_tags(user_id: int) -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, keyword, kind
            FROM user_role_tags
            WHERE user_id = %s
            ORDER BY kind, id
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def find_user_role_tag(user_id: int, kind: str, keyword: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, keyword, kind
            FROM user_role_tags
            WHERE user_id = %s AND kind = %s AND keyword = %s
            """,
            (user_id, kind, keyword),
        ).fetchone()
    return dict(row) if row else None


def insert_user_role_tag(user_id: int, keyword: str, kind: str) -> dict:
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO user_role_tags (user_id, keyword, kind)
            VALUES (%s, %s, %s)
            RETURNING id, keyword, kind
            """,
            (user_id, keyword, kind),
        ).fetchone()
    return dict(row)


def delete_user_role_tag(user_id: int, tag_id: int) -> bool:
    with db_transaction() as conn:
        row = conn.execute(
            """
            DELETE FROM user_role_tags
            WHERE user_id = %s AND id = %s
            RETURNING id
            """,
            (user_id, tag_id),
        ).fetchone()
    return row is not None


def get_user_role_tag(user_id: int, tag_id: int) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, keyword, kind
            FROM user_role_tags
            WHERE user_id = %s AND id = %s
            """,
            (user_id, tag_id),
        ).fetchone()
    return dict(row) if row else None


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
            SELECT c.country, c.name AS company_name, j.*
            FROM companies c
            JOIN matching_jobs j ON j.company_id = c.id
            WHERE ({clauses})
              AND j.matches_default_filter = 0
              AND (j.closed_at IS NULL OR j.closed_at = '')
            ORDER BY c.country, c.name, j.title
            """,
            params,
        ).fetchall()
    jobs: list[dict] = []
    for row in rows:
        data = dict(row)
        job = _job_row(data)
        job["country"] = data.get("country") or ""
        job["company_name"] = data.get("company_name") or ""
        jobs.append(job)
    return jobs
