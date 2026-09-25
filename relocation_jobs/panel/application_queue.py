from __future__ import annotations

import math

from relocation_jobs.catalog.repo import get_company, get_job_by_url
from relocation_jobs.core.db import _normalize_url
from relocation_jobs.core.location_tags import country_label
from relocation_jobs.mcp import repo as mcp_repo
from relocation_jobs.panel.flatten import PanelContext
from relocation_jobs.panel.tracking import job_dict, tracked_job_dict
from relocation_jobs.positions.queue import (
    APPLICATION_STATE_APPLY,
    APPLICATION_STATE_APPLIED,
    APPLICATION_STATE_REJECTED,
)
from relocation_jobs.positions import repo as positions_repo
from relocation_jobs.users.repo import load_job_status_history

DEFAULT_APPLICATIONS_PAGE_SIZE = 20
MAX_APPLICATIONS_PAGE_SIZE = 20


def clamp_applications_page(page: int | None, page_size: int | None) -> tuple[int, int]:
    page_n = max(1, int(page or 1))
    size = int(page_size or DEFAULT_APPLICATIONS_PAGE_SIZE)
    size = max(1, min(size, MAX_APPLICATIONS_PAGE_SIZE))
    return page_n, size


def _pagination_meta(*, page: int, page_size: int, total: int) -> dict:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_more": page * page_size < total,
    }


def _hydrate_tracked_job(
    *,
    country_key: str,
    company_name: str,
    job_url: str,
    row: dict,
    ctx: PanelContext,
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


def _page_context(user_id: int, rows: list[dict], *, country: str | None) -> PanelContext:
    scope = (country or "").strip().lower() or None
    if scope == "all":
        scope = None
    job_tracking: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (
            row["country"],
            row["company_name"],
            _normalize_url(row.get("job_url") or ""),
        )
        job_tracking[key] = dict(row)
    return PanelContext(
        user_id=user_id,
        job_tracking=job_tracking,
        status_history=load_job_status_history(user_id, country=scope),
        mcp_applications=mcp_repo.load_application_summaries(user_id, country=scope),
    )


def _list_state_page(
    user_id: int,
    state: str,
    *,
    country: str | None,
    page: int,
    page_size: int | None,
) -> dict:
    page_n, size = clamp_applications_page(page, page_size)
    total = positions_repo.count_application_state(
        user_id, state, country=country,
    )
    offset = (page_n - 1) * size
    rows = positions_repo.list_application_state_rows(
        user_id,
        state,
        country=country,
        offset=offset,
        limit=size,
    )
    ctx = _page_context(user_id, rows, country=country)
    jobs = [
        _hydrate_tracked_job(
            country_key=row["country"],
            company_name=row["company_name"],
            job_url=_normalize_url(row.get("job_url") or ""),
            row=row,
            ctx=ctx,
        )
        for row in rows
    ]
    return {
        "jobs": jobs,
        "meta": _pagination_meta(page=page_n, page_size=size, total=total),
    }


def count_application_states(
    user_id: int,
    *,
    country: str | None = None,
) -> dict[str, int]:
    return positions_repo.count_application_states(user_id, country=country)


def list_application_queue_positions(
    user_id: int,
    *,
    country: str | None = None,
    page: int = 1,
    page_size: int | None = DEFAULT_APPLICATIONS_PAGE_SIZE,
) -> dict:
    return _list_state_page(
        user_id,
        APPLICATION_STATE_APPLY,
        country=country,
        page=page,
        page_size=page_size or DEFAULT_APPLICATIONS_PAGE_SIZE,
    )


def list_applied_positions(
    user_id: int,
    *,
    country: str | None = None,
    page: int = 1,
    page_size: int | None = DEFAULT_APPLICATIONS_PAGE_SIZE,
) -> dict:
    return _list_state_page(
        user_id,
        APPLICATION_STATE_APPLIED,
        country=country,
        page=page,
        page_size=page_size or DEFAULT_APPLICATIONS_PAGE_SIZE,
    )


def list_rejected_positions(
    user_id: int,
    *,
    country: str | None = None,
    page: int = 1,
    page_size: int | None = DEFAULT_APPLICATIONS_PAGE_SIZE,
) -> dict:
    return _list_state_page(
        user_id,
        APPLICATION_STATE_REJECTED,
        country=country,
        page=page,
        page_size=page_size or DEFAULT_APPLICATIONS_PAGE_SIZE,
    )
