from __future__ import annotations

from relocation_jobs.core.db import _utc_now, db_read, db_transaction
from relocation_jobs.opportunities.types import OpportunityRow


def ensure_user_preferences_row(user_id: int) -> None:
    now = _utc_now()
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, updated_at)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, now),
        )


def list_user_opportunity_rows(user_id: int) -> list[OpportunityRow]:
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT country, company_name, newest_fetched,
                   COALESCE(revealed_job_count, 0) AS revealed_job_count,
                   COALESCE(engaged, 0) AS engaged
            FROM user_opportunities
            WHERE user_id = %s
            ORDER BY newest_fetched DESC, company_name ASC
            """,
            (user_id,),
        ).fetchall()
    return [
        OpportunityRow(
            country=(row.get("country") or "").strip().lower(),
            company_name=(row.get("company_name") or "").strip(),
            newest_fetched=(row.get("newest_fetched") or "").strip(),
            revealed_job_count=int(row.get("revealed_job_count") or 0),
            engaged=bool(row.get("engaged")),
        )
        for row in rows
        if (row.get("company_name") or "").strip()
    ]


def mark_opportunity_refresh_attempted(user_id: int) -> None:
    now = _utc_now()
    ensure_user_preferences_row(user_id)
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET opportunities_refreshed_at = %s
            WHERE user_id = %s
            """,
            (now, user_id),
        )


def needs_opportunity_bootstrap(user_id: int) -> bool:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT opportunities_refreshed_at
            FROM user_preferences WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return True
    return not (row.get("opportunities_refreshed_at") or "").strip()


def list_user_opportunity_companies(user_id: int, *, country: str | None = None) -> list[dict]:
    sql = """
        SELECT country, company_name, newest_fetched, updated_at,
               COALESCE(revealed_job_count, 0) AS revealed_job_count,
               COALESCE(engaged, 0) AS engaged
        FROM user_opportunities
        WHERE user_id = %s
    """
    params: list = [user_id]
    if country and country != "all":
        sql += " AND country = %s"
        params.append(country.strip().lower())
    sql += " ORDER BY newest_fetched DESC, company_name ASC"
    with db_read() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def count_user_opportunities(user_id: int) -> int:
    with db_read() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM user_opportunities WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return int((row or {}).get("n") or 0)
