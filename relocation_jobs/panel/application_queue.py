from __future__ import annotations

from collections.abc import Callable

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
) -> dict:
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


def _list_positions(
    user_id: int,
    *,
    country: str | None,
    include_row: Callable[[dict], bool],
    sort_key: Callable[[dict], tuple],
    reverse: bool = False,
) -> list[dict]:
    scope = (country or "").strip().lower() or None
    ctx = load_context(user_id, country_key=scope)
    jobs: list[dict] = []
    for (country_key, company_name, job_url), row in (ctx.job_tracking or {}).items():
        if not include_row(row):
            continue
        jobs.append(
            _hydrate_tracked_job(
                country_key=country_key,
                company_name=company_name,
                job_url=job_url,
                row=row,
                ctx=ctx,
            )
        )
    jobs.sort(key=sort_key, reverse=reverse)
    return jobs


def list_application_queue_positions(
    user_id: int,
    *,
    country: str | None = None,
) -> list[dict]:
    return _list_positions(
        user_id,
        country=country,
        include_row=is_active_application_queue_row,
        sort_key=_queue_sort_key,
    )


def list_applied_positions(
    user_id: int,
    *,
    country: str | None = None,
) -> list[dict]:
    return _list_positions(
        user_id,
        country=country,
        include_row=lambda row: bool(row.get("applied")) and not as_bool(row.get("not_for_me")),
        sort_key=_applied_sort_key,
        reverse=True,
    )
