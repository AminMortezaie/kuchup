from __future__ import annotations

from datetime import datetime, timezone

from relocation_jobs.broadcast.types import PositionAssignment
from relocation_jobs.core.db import _utc_now, db_read, db_transaction


def current_period_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _assignment(row: dict) -> PositionAssignment:
    return PositionAssignment(
        period_key=(row.get("period_key") or "").strip(),
        country=(row.get("country") or "").strip().lower(),
        company_name=(row.get("company_name") or "").strip(),
        job_key=(row.get("job_key") or "").strip(),
        job_url=(row.get("job_url") or "").strip(),
        job_title=(row.get("job_title") or "").strip(),
        assigned_at=(row.get("assigned_at") or "").strip(),
        consumed_at=(row.get("consumed_at") or "").strip() or None,
    )


def list_assignments(
    user_id: int,
    *,
    period_key: str | None = None,
) -> list[PositionAssignment]:
    period = period_key or current_period_key()
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT period_key, country, company_name, job_key, job_url,
                   job_title, assigned_at, consumed_at
            FROM position_broadcast_assignments
            WHERE user_id = %s AND period_key = %s
            ORDER BY assigned_at ASC
            """,
            (user_id, period),
        ).fetchall()
    return [_assignment(dict(row)) for row in rows]


def consumed_count(user_id: int, *, period_key: str | None = None) -> int:
    period = period_key or current_period_key()
    with db_read() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM position_broadcast_assignments
            WHERE user_id = %s AND period_key = %s AND consumed_at IS NOT NULL
            """,
            (user_id, period),
        ).fetchone()
    return int((row or {}).get("n") or 0)


def ensure_company_assignments(
    user_id: int,
    country: str,
    company_name: str,
    jobs: list[dict],
    *,
    active_target: int,
    period_key: str | None = None,
) -> list[PositionAssignment]:
    period = period_key or current_period_key()
    country_key = country.strip().lower()
    name = company_name.strip()
    now = _utc_now()
    current_keys = {
        (job.get("idempotency_key") or "").strip()
        for job in jobs
        if (job.get("idempotency_key") or "").strip()
    }
    with db_transaction() as conn:
        rows = conn.execute(
            """
            SELECT job_key, consumed_at
            FROM position_broadcast_assignments
            WHERE user_id = %s AND period_key = %s
              AND country = %s AND lower(company_name) = lower(%s)
            """,
            (user_id, period, country_key, name),
        ).fetchall()
        assigned = {(row.get("job_key") or "").strip() for row in rows}
        consumed = sum(1 for row in rows if (row.get("consumed_at") or "").strip())
        target = max(0, int(active_target) - consumed)
        active = sum(
            1
            for row in rows
            if not (row.get("consumed_at") or "").strip()
            and (row.get("job_key") or "").strip() in current_keys
        )
        for job in jobs:
            if active >= target:
                break
            job_key = (job.get("idempotency_key") or "").strip()
            if not job_key or job_key in assigned:
                continue
            inserted = conn.execute(
                """
                INSERT INTO position_broadcast_assignments (
                    user_id, period_key, country, company_name, job_key,
                    job_url, job_title, assigned_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING job_key
                """,
                (
                    user_id,
                    period,
                    country_key,
                    name,
                    job_key,
                    (job.get("url") or "").strip(),
                    (job.get("title") or "").strip(),
                    now,
                ),
            ).fetchone()
            if inserted:
                assigned.add(job_key)
                active += 1
    return list_assignments(user_id, period_key=period)


def assign_position(
    user_id: int,
    country: str,
    company_name: str,
    job: dict,
    *,
    period_key: str | None = None,
) -> bool:
    period = period_key or current_period_key()
    job_key = (job.get("idempotency_key") or "").strip()
    if not job_key:
        return False
    with db_transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO position_broadcast_assignments (
                user_id, period_key, country, company_name, job_key,
                job_url, job_title, assigned_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING job_key
            """,
            (
                user_id,
                period,
                country.strip().lower(),
                company_name.strip(),
                job_key,
                (job.get("url") or "").strip(),
                (job.get("title") or "").strip(),
                _utc_now(),
            ),
        ).fetchone()
    return bool(row)


def mark_assignment_consumed(
    user_id: int,
    *,
    country: str,
    company_name: str,
    job_key: str,
    job_url: str,
    job_title: str,
    action_kind: str,
    period_key: str | None = None,
) -> bool:
    period = period_key or current_period_key()
    now = _utc_now()
    country_key = country.strip().lower()
    name = company_name.strip()
    key = job_key.strip()
    with db_transaction() as conn:
        existing = conn.execute(
            """
            SELECT consumed_at FROM position_broadcast_assignments
            WHERE user_id = %s AND period_key = %s AND country = %s
              AND lower(company_name) = lower(%s) AND job_key = %s
            """,
            (user_id, period, country_key, name, key),
        ).fetchone()
        already_consumed = bool(existing and (existing.get("consumed_at") or "").strip())
        conn.execute(
            """
            INSERT INTO position_broadcast_assignments (
                user_id, period_key, country, company_name, job_key,
                job_url, job_title, assigned_at, consumed_at, action_kind
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, period_key, country, company_name, job_key)
            DO UPDATE SET consumed_at = COALESCE(
                    position_broadcast_assignments.consumed_at,
                    EXCLUDED.consumed_at
                ),
                action_kind = COALESCE(
                    position_broadcast_assignments.action_kind,
                    EXCLUDED.action_kind
                )
            """,
            (
                user_id,
                period,
                country_key,
                name,
                key,
                job_url.strip(),
                job_title.strip(),
                now,
                now,
                action_kind.strip(),
            ),
        )
        conn.execute(
            """
            UPDATE user_opportunities
            SET engaged = 1, updated_at = %s
            WHERE user_id = %s AND country = %s AND lower(company_name) = lower(%s)
            """,
            (now, user_id, country_key, name),
        )
    return not already_consumed
