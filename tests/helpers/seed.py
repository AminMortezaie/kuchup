from __future__ import annotations

import copy
import json
from pathlib import Path

from relocation_jobs.core.job_identity import job_idempotency_key, stamp_job_identity
from relocation_jobs.core.db import _utc_now, db_transaction
from relocation_jobs.catalog.repo import get_company
from relocation_jobs.catalog.repo import sync_company_board_to_catalog
from relocation_jobs.catalog.repo import sync_country_catalog
from relocation_jobs.scrape.merge import merge_matching_jobs
from relocation_jobs.broadcast import repo as broadcast_repo
from relocation_jobs.catalog.repo import list_companies_for_opportunity_match, list_jobs_for_company_keys
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.opportunities.types import OpportunityRow
from relocation_jobs.users.entitlements import free_board_company_cap, free_jobs_per_company


def seed_country(country_key: str, fixture_path: Path) -> dict:
    data = copy.deepcopy(json.loads(fixture_path.read_text(encoding="utf-8")))
    for company in data.get("companies") or []:
        for job in company.get("matching_jobs") or []:
            stamp_job_identity(job)
            job.setdefault("idempotency_key", job_idempotency_key(job.get("url", "")))
    sync_country_catalog(country_key, data)
    return data


def replace_matching_jobs(country_key: str, company_name: str, jobs: list[dict]) -> None:
    company = get_company(country_key, company_name)
    if company is None:
        raise LookupError(f"Company not found: {company_name}")
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog(country_key, company)


def append_matching_jobs(
    country_key: str,
    company_name: str,
    extra: list[dict],
) -> list[dict]:
    company = get_company(country_key, company_name)
    if company is None:
        raise LookupError(f"Company not found: {company_name}")
    jobs = list(company.get("matching_jobs") or [])
    for job in extra:
        stamp_job_identity(job)
        jobs.append(job)
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog(country_key, company)
    return jobs


def merge_and_save_jobs(country_key: str, company_name: str, scraped: list[dict]) -> list[dict]:
    company = get_company(country_key, company_name)
    if company is None:
        raise LookupError(f"Company not found: {company_name}")
    merged, _, _, _, _ = merge_matching_jobs(company.get("matching_jobs") or [], scraped)
    company["matching_jobs"] = merged
    sync_company_board_to_catalog(country_key, company)
    return merged


def replace_user_opportunities(user_id: int, rows: list[OpportunityRow]) -> int:
    now = _utc_now()
    with db_transaction() as conn:
        conn.execute("DELETE FROM user_opportunities WHERE user_id = %s", (user_id,))
        for row in rows:
            conn.execute(
                """
                INSERT INTO user_opportunities (
                    user_id, country, company_name, newest_fetched, updated_at,
                    revealed_job_count, engaged
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    row.country,
                    row.company_name,
                    row.newest_fetched or "",
                    now,
                    max(0, int(row.revealed_job_count)),
                    1 if row.engaged else 0,
                ),
            )
        conn.execute(
            """
            UPDATE user_preferences
            SET opportunities_refreshed_at = %s
            WHERE user_id = %s
            """,
            (now, user_id),
        )
    return len(rows)


def ensure_company_assignments(
    user_id: int,
    country: str,
    company_name: str,
    jobs: list[dict],
    *,
    active_target: int,
    period_key: str | None = None,
):
    period = period_key or broadcast_repo.current_period_key()
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
    return broadcast_repo.list_assignments(user_id, period_key=period)


def seed_free_assignments(user_id: int, countries: list[str]) -> int:
    opportunities_repo.save_user_preferences(
        user_id,
        target_countries=countries,
        preferences_confirmed=True,
    )
    raw = list_companies_for_opportunity_match(list(countries))
    ranked = sorted(
        [item for item in raw if int(item.get("open_job_count") or 0) > 0],
        key=lambda item: (item.get("newest_fetched") or "", (item.get("company_name") or "").lower()),
        reverse=True,
    )
    chosen = ranked[: free_board_company_cap()]
    rows = [
        OpportunityRow(
            country=item["country"],
            company_name=item["company_name"],
            newest_fetched=item.get("newest_fetched") or "",
        )
        for item in chosen
    ]
    replace_user_opportunities(user_id, rows)
    jobs_by_company = list_jobs_for_company_keys(
        [(row.country, row.company_name) for row in rows]
    )
    per_company = free_jobs_per_company()
    for row in rows:
        ensure_company_assignments(
            user_id,
            row.country,
            row.company_name,
            jobs_by_company.get((row.country, row.company_name.lower()), []),
            active_target=per_company,
        )
    return len(rows)
