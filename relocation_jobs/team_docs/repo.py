from __future__ import annotations

from relocation_jobs.core.db import _utc_now, db_read, db_transaction


def _folder_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "parent_id": int(row["parent_id"]) if row["parent_id"] is not None else None,
        "slug": row["slug"],
        "title": row["title"],
        "path": row["path"],
        "sort_order": int(row["sort_order"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _doc_row(row, *, include_body: bool) -> dict:
    payload = {
        "id": int(row["id"]),
        "folder_id": int(row["folder_id"]),
        "slug": row["slug"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_body:
        payload["body"] = row["body"] or ""
    return payload


def list_folders() -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, parent_id, slug, title, path, sort_order, created_at, updated_at
            FROM team_doc_folders
            ORDER BY sort_order ASC, path ASC
            """
        ).fetchall()
    return [_folder_row(row) for row in rows]


def get_folder(folder_id: int) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, parent_id, slug, title, path, sort_order, created_at, updated_at
            FROM team_doc_folders
            WHERE id = %s
            """,
            (folder_id,),
        ).fetchone()
    return _folder_row(row) if row else None


def list_doc_summaries() -> list[dict]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT id, folder_id, slug, title, created_at, updated_at
            FROM team_docs
            ORDER BY title ASC, id ASC
            """
        ).fetchall()
    return [_doc_row(row, include_body=False) for row in rows]


def get_doc(doc_id: int) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, folder_id, slug, title, body, created_at, updated_at
            FROM team_docs
            WHERE id = %s
            """,
            (doc_id,),
        ).fetchone()
    return _doc_row(row, include_body=True) if row else None


def find_doc_in_folder(folder_id: int, slug: str) -> dict | None:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT id, folder_id, slug, title, created_at, updated_at
            FROM team_docs
            WHERE folder_id = %s AND slug = %s
            """,
            (folder_id, slug),
        ).fetchone()
    return _doc_row(row, include_body=False) if row else None


def insert_doc(*, folder_id: int, slug: str, title: str, body: str) -> dict:
    now = _utc_now()
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO team_docs (folder_id, slug, title, body, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, folder_id, slug, title, body, created_at, updated_at
            """,
            (folder_id, slug, title, body, now, now),
        ).fetchone()
    return _doc_row(row, include_body=True)


def update_doc(
    doc_id: int,
    *,
    folder_id: int,
    slug: str,
    title: str,
    body: str,
) -> dict | None:
    now = _utc_now()
    with db_transaction() as conn:
        row = conn.execute(
            """
            UPDATE team_docs
            SET folder_id = %s, slug = %s, title = %s, body = %s, updated_at = %s
            WHERE id = %s
            RETURNING id, folder_id, slug, title, body, created_at, updated_at
            """,
            (folder_id, slug, title, body, now, doc_id),
        ).fetchone()
    return _doc_row(row, include_body=True) if row else None


def delete_doc(doc_id: int) -> bool:
    with db_transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM team_docs WHERE id = %s",
            (doc_id,),
        )
        return cursor.rowcount > 0
