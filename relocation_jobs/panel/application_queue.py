from __future__ import annotations

from relocation_jobs.catalog.repo import get_company, get_job_by_url
from relocation_jobs.core.location_tags import country_label
from relocation_jobs.panel.service import load_context
from relocation_jobs.panel.tracking import job_dict, tracked_job_dict
from relocation_jobs.positions.queue import is_active_application_queue_row
from relocation_jobs.shared.coerce import as_bool


def _queue_sort_key(job: dict) -> tuple:
    return (
        not bool(job.get("pinned")),
        not bool(job.get("looking_to_apply")),
        (job.get("company") or "").casefold(),
        (job.get("title") or "").casefold(),
        (job.get("url") or ""),
    )


def _applied_sort_key(job: dict) -> tuple:
    return (
        (job.get("applied_at") or job.get("applied_date") or ""),
        (job.get("company") or "").casefold(),
        (job.get("title") or "").casefold(),
    )


def _hydrate_tracked_job(
    *,
    country_key: str,
    company_name: str,
    job_url: str,
    row: dict,
    ctx,
) -> dict | None:
    company = get_company(country_key, company_name) or {"name": company_name}
    label = country_label(country_key)
    job = get_job_by_url(
        job_url,
        company_name=company_name,
        country_key=country_key,
    )
    if job is not None:
        return job_dict(
            job,
            company_name=company_name,
            company=company,
            country_key=country_key,
            country_label=label,
            job_tracking=ctx.job_tracking,
            status_history=ctx.status_history,
            mcp_applications=ctx.mcp_applications,
        )
    track = {
        **row,
        "job_url": job_url,
        "job_title": row.get("job_title") or "",
    }
    return tracked_job_dict(
        track,
        company_name=company_name,
        company=company,
        country_key=country_key,
        country_label=label,
        status_history=ctx.status_history,
        mcp_applications=ctx.mcp_applications,
    )


def list_application_queue_positions(
    user_id: int,
    *,
    country: str | None = None,
) -> list[dict]:
    scope = (country or "").strip().lower() or None
    ctx = load_context(user_id, country_key=scope)
    jobs: list[dict] = []
    for (country_key, company_name, job_url), row in (ctx.job_tracking or {}).items():
        if not is_active_application_queue_row(row):
            continue
        item = _hydrate_tracked_job(
            country_key=country_key,
            company_name=company_name,
            job_url=job_url,
            row=row,
            ctx=ctx,
        )
        if item:
            jobs.append(item)
    jobs.sort(key=_queue_sort_key)
    return jobs


def list_applied_positions(
    user_id: int,
    *,
    country: str | None = None,
) -> list[dict]:
    scope = (country or "").strip().lower() or None
    ctx = load_context(user_id, country_key=scope)
    jobs: list[dict] = []
    for (country_key, company_name, job_url), row in (ctx.job_tracking or {}).items():
        if not bool(row.get("applied")):
            continue
        if as_bool(row.get("not_for_me")):
            continue
        item = _hydrate_tracked_job(
            country_key=country_key,
            company_name=company_name,
            job_url=job_url,
            row=row,
            ctx=ctx,
        )
        if item:
            jobs.append(item)
    jobs.sort(key=_applied_sort_key, reverse=True)
    return jobs
