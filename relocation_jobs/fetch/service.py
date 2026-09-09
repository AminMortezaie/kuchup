from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from relocation_jobs.core.scrape_cancel import FetchCancelled
from relocation_jobs.fetch import repo
from relocation_jobs.fetch.types import AttemptStatus, is_infra_fetch_error

_ERROR_RE = re.compile(r" — Error: (.+)$")


def _today() -> str:
    return date.today().isoformat()


def _company_ats_type(company: dict) -> str:
    return (company.get("ats_type") or "").strip() or "generic"


def _mark_fetch_problem(company: dict) -> None:
    company["fetch_problem"] = True
    company["fetch_problem_date"] = _today()
    company["fetch_ok"] = False
    company.pop("fetch_ok_date", None)


def _record_finish(
    attempt_id: int,
    *,
    status: AttemptStatus,
    error_message: str | None = None,
    jobs_total: int | None = None,
    jobs_new: int | None = None,
    message: str | None = None,
) -> None:
    repo.update_attempt(
        attempt_id,
        status=status,
        error_message=error_message,
        jobs_total=jobs_total,
        jobs_new=jobs_new,
        message=message,
    )


def start_company_attempt(
    company: dict,
    *,
    country_key: str,
    fetch_run_id: int | None = None,
) -> int:
    return repo.insert_attempt(
        country=country_key,
        company_name=company.get("name") or "",
        careers_url=company.get("careers_url") or "",
        ats_type=_company_ats_type(company),
        fetch_run_id=fetch_run_id,
    )


def finish_cancelled_attempt(attempt_id: int) -> None:
    _record_finish(attempt_id, status=AttemptStatus.CANCELLED, message="cancelled")


def finish_company_attempt(
    attempt_id: int,
    company: dict,
    msg: str,
    new_count: int,
) -> tuple[str, int]:
    err_match = _ERROR_RE.search(msg)
    if err_match:
        error_message = err_match.group(1)
        if is_infra_fetch_error(error_message):
            company.pop("fetch_problem", None)
            company.pop("fetch_problem_date", None)
        else:
            _mark_fetch_problem(company)
        jobs = company.get("matching_jobs") or []
        _record_finish(
            attempt_id,
            status=AttemptStatus.ERROR,
            error_message=error_message,
            jobs_total=len(jobs),
            jobs_new=0,
            message=msg,
        )
        return msg, 0

    jobs = company.get("matching_jobs") or []
    _record_finish(
        attempt_id,
        status=AttemptStatus.OK,
        jobs_total=len(jobs),
        jobs_new=new_count,
        message=msg,
    )
    return msg, new_count


async def fetch_company(
    client,
    company: dict,
    index: int,
    total: int,
    *,
    country_key: str,
    process_company: Callable,
    sync_board,
    enrich_only: bool,
    skip_enriched: bool,
    enrich_concurrency: int,
    fetch_run_id: int | None = None,
) -> tuple[str, int]:
    attempt_id = start_company_attempt(
        company, country_key=country_key, fetch_run_id=fetch_run_id,
    )
    try:
        msg, new_count = await process_company(
            client,
            company,
            index,
            total,
            sync_board=sync_board,
            enrich_only=enrich_only,
            skip_enriched=skip_enriched,
            enrich_concurrency=enrich_concurrency,
            catalog_country=country_key,
        )
    except FetchCancelled:
        finish_cancelled_attempt(attempt_id)
        raise
    return finish_company_attempt(attempt_id, company, msg, new_count)
