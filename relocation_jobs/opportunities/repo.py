from __future__ import annotations

import json

from relocation_jobs.core.db import _utc_now, db_read, db_transaction
from relocation_jobs.opportunities.types import DEFAULT_TARGET_COUNTRIES, OpportunityRow, UserPreferences


def _parse_json_list(raw: str | None) -> tuple[str, ...]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, list):
        return ()
    out: list[str] = []
    for item in data:
        value = str(item or "").strip().lower()
        if value and value not in out:
            out.append(value)
    return tuple(out)


def get_user_preferences(user_id: int) -> UserPreferences:
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT target_countries_json, seniority, keywords_json, remote_ok,
                   preferences_confirmed, opportunities_refreshed_at
            FROM user_preferences WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return UserPreferences(user_id=user_id)
    return UserPreferences(
        user_id=user_id,
        target_countries=_parse_json_list(row.get("target_countries_json")),
        seniority=(row.get("seniority") or "").strip().lower(),
        keywords=_parse_json_list(row.get("keywords_json")),
        remote_ok=bool(row.get("remote_ok")),
        preferences_confirmed=bool(row.get("preferences_confirmed")),
        opportunities_refreshed_at=(row.get("opportunities_refreshed_at") or "").strip() or None,
    )


def save_user_preferences(
    user_id: int,
    *,
    target_countries: list[str] | tuple[str, ...],
    seniority: str = "",
    keywords: list[str] | tuple[str, ...] = (),
    remote_ok: bool = False,
    preferences_confirmed: bool = True,
) -> UserPreferences:
    countries = [c.strip().lower() for c in target_countries if (c or "").strip()]
    keyword_list = [k.strip().lower() for k in keywords if (k or "").strip()]
    now = _utc_now()
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, target_countries_json, seniority, keywords_json, remote_ok,
                preferences_confirmed, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                target_countries_json = EXCLUDED.target_countries_json,
                seniority = EXCLUDED.seniority,
                keywords_json = EXCLUDED.keywords_json,
                remote_ok = EXCLUDED.remote_ok,
                preferences_confirmed = EXCLUDED.preferences_confirmed,
                updated_at = EXCLUDED.updated_at
            """,
            (
                user_id,
                json.dumps(countries),
                (seniority or "").strip().lower(),
                json.dumps(keyword_list),
                1 if remote_ok else 0,
                1 if preferences_confirmed else 0,
                now,
            ),
        )
    return get_user_preferences(user_id)


def list_user_ids_for_country(country: str) -> list[int]:
    key = country.strip().lower()
    if not key:
        return []
    default_countries = frozenset(DEFAULT_TARGET_COUNTRIES)
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, p.target_countries_json
            FROM users u
            LEFT JOIN user_preferences p ON p.user_id = u.id
            """
        ).fetchall()
    out: list[int] = []
    for row in rows:
        countries = _parse_json_list(row.get("target_countries_json"))
        effective = countries if countries else default_countries
        if key in effective:
            out.append(int(row["user_id"]))
    return out


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
