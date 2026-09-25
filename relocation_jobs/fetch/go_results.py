from __future__ import annotations

import json

from relocation_jobs.core.db import db_transaction, get_connection


def list_pending_http_results(*, limit: int = 20, result_id: int | None = None) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    where = "r.merge_processed_at IS NULL"
    params: list = []
    if result_id is not None:
        where += " AND r.id = %s"
        params.append(int(result_id))
    params.append(limit)
    rows = get_connection().execute(
        f"""
        SELECT r.id, r.fetch_run_id, r.company_id, r.status, r.error, r.jobs_json,
               r.fetched_at, w.country_key, w.name, w.ats_type, w.ats_url
        FROM fetch_http_results r
        JOIN fetch_http_work w
          ON w.fetch_run_id = r.fetch_run_id AND w.company_id = r.company_id
        WHERE {where}
        ORDER BY r.id ASC
        LIMIT %s
        """,
        tuple(params),
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        data = dict(row)
        jobs_raw = data.pop("jobs_json", None)
        jobs: list[dict] = []
        if jobs_raw:
            try:
                parsed = json.loads(jobs_raw)
                if isinstance(parsed, list):
                    jobs = parsed
            except (json.JSONDecodeError, TypeError):
                jobs = []
        data["jobs"] = jobs
        out.append(data)
    return out


def get_pending_http_result(result_id: int) -> dict | None:
    rows = list_pending_http_results(limit=1, result_id=result_id)
    return rows[0] if rows else None


def mark_http_result_processed(result_id: int) -> None:
    from datetime import datetime, timezone

    processed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE fetch_http_results
            SET merge_processed_at = %s
            WHERE id = %s AND merge_processed_at IS NULL
            """,
            (processed_at, int(result_id)),
        )


def run_merge_complete(run_id: int) -> bool:
    row = get_connection().execute(
        """
        SELECT COUNT(*) AS pending
        FROM fetch_http_results
        WHERE fetch_run_id = %s AND merge_processed_at IS NULL
        """,
        (int(run_id),),
    ).fetchone()
    pending = int((row or {}).get("pending") or 0)
    if pending:
        return False
    run = get_connection().execute(
        "SELECT status, country FROM fetch_runs WHERE id = %s",
        (int(run_id),),
    ).fetchone()
    if not run or (run.get("status") or "") == "running":
        return False
    return True
