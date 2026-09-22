from __future__ import annotations

from relocation_jobs.core.db import _utc_now, db_read, db_transaction


def _doc_row(row, *, include_body: bool) -> dict:
    payload = {
        "id": int(row["id"]),
        "folder": row["folder"],
        "slug": row["slug"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "created_by_user_id": row["created_by_user_id"],
        "updated_by_user_id": row["updated_by_user_id"],
    }
    if include_body:
        payload["body"] = row["body"] or ""
    return payload


def list_doc_summaries() -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, folder, slug, title, created_at, updated_at,
                   created_by_user_id, updated_by_user_id
            FROM team_docs
            ORDER BY folder ASC, LOWER(slug) ASC, id ASC
            """
        ).fetchall()
    return [_doc_row(row, include_body=False) for row in rows]


def get_doc(doc_id: int) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, folder, slug, title, body, created_at, updated_at,
                   created_by_user_id, updated_by_user_id
            FROM team_docs
            WHERE id = %s
            """,
            (doc_id,),
        ).fetchone()
    return _doc_row(row, include_body=True) if row else None


def find_doc_in_folder(folder: str, slug: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, folder, slug, title, created_at, updated_at,
                   created_by_user_id, updated_by_user_id
            FROM team_docs
            WHERE folder = %s AND slug = %s
            """,
            (folder, slug),
        ).fetchone()
    return _doc_row(row, include_body=False) if row else None


def insert_doc(
    *,
    folder: str,
    slug: str,
    title: str,
    body: str,
    editor_user_id: int,
) -> dict:
    now = _utc_now()
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO team_docs (
                folder, slug, title, body, created_at, updated_at,
                created_by_user_id, updated_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, folder, slug, title, body, created_at, updated_at,
                      created_by_user_id, updated_by_user_id
            """,
            (folder, slug, title, body, now, now, editor_user_id, editor_user_id),
        ).fetchone()
    return _doc_row(row, include_body=True)


def update_doc(
    doc_id: int,
    *,
    folder: str,
    slug: str,
    title: str,
    body: str,
    editor_user_id: int,
) -> dict | None:
    now = _utc_now()
    with db_transaction() as conn:
        row = conn.execute(
            """
            UPDATE team_docs
            SET folder = %s, slug = %s, title = %s, body = %s, updated_at = %s,
                updated_by_user_id = %s
            WHERE id = %s
            RETURNING id, folder, slug, title, body, created_at, updated_at,
                      created_by_user_id, updated_by_user_id
            """,
            (folder, slug, title, body, now, editor_user_id, doc_id),
        ).fetchone()
    return _doc_row(row, include_body=True) if row else None


def delete_doc(doc_id: int) -> bool:
    with db_transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM team_docs WHERE id = %s",
            (doc_id,),
        )
        return cursor.rowcount > 0
