from __future__ import annotations

import re

from relocation_jobs.fetch import repo
from relocation_jobs.fetch.types import AttemptStatus

_ERROR_RE = re.compile(r" — Error: (.+)$")


def _company_ats_type(company: dict) -> str:
    return (company.get("ats_type") or "").strip() or "generic"


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
    jobs = company.get("matching_jobs") or []
    err_match = _ERROR_RE.search(msg)
    if err_match:
        _record_finish(
            attempt_id,
            status=AttemptStatus.ERROR,
            error_message=err_match.group(1),
            jobs_total=len(jobs),
            jobs_new=0,
            message=msg,
        )
        return msg, 0
    _record_finish(
        attempt_id,
        status=AttemptStatus.OK,
        jobs_total=len(jobs),
        jobs_new=new_count,
        message=msg,
    )
    return msg, new_count
