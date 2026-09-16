from __future__ import annotations

import asyncio
import os

from relocation_jobs.core.scrape_cancel import FetchCancelled
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch.country_runner import companies_to_fetch, stamp_country_fetch_meta
from relocation_jobs.fetch.pipeline import fetch_and_persist_company
from relocation_jobs.fetch.timeouts import (
    company_timeout_seconds,
    fetch_job_max_attempts,
    fetch_job_retry_seconds,
    fetch_job_stale_seconds,
)
from relocation_jobs.fetch.types import FetchJob, FetchJobStatus


def fetch_worker_id() -> str:
    raw = (os.environ.get("FETCH_WORKER_ID") or "").strip()
    if raw:
        return raw
    return f"{os.uname().nodename}:{os.getpid()}"


def enqueue_country_company_jobs(
    country_key: str,
    *,
    fetch_run_id: int | None = None,
    user_id: int | None = None,
    ats_type: str | None = None,
) -> int:
    companies = companies_to_fetch(country_key, ats_type=ats_type)
    max_attempts = fetch_job_max_attempts()
    for stub in companies:
        name = (stub.get("name") or "").strip()
        if not name:
            continue
        fetch_repo.enqueue_company_fetch_job(
            country=country_key,
            company_name=name,
            fetch_run_id=fetch_run_id,
            user_id=user_id,
            payload={"ats_type": (stub.get("ats_type") or "").strip()},
            max_attempts=max_attempts,
        )
    return len(companies)


def _finish_claimed_job(job: FetchJob, *, error: str | None):
    if error is None:
        return fetch_repo.complete_fetch_job(job.id)
    return fetch_repo.fail_fetch_job(
        job.id,
        error_message=error,
        retry_seconds=fetch_job_retry_seconds(),
    )


async def _process_claimed_job(
    client,
    job: FetchJob,
    *,
    on_log,
    on_company_result,
) -> tuple[int, bool, bool]:
    name = (job.company_name or "").strip()
    if not name:
        _finish_claimed_job(job, error="missing company_name")
        return 0, False, True
    try:
        msg, new_count = await asyncio.wait_for(
            fetch_and_persist_company(
                client,
                job.country,
                name,
                fetch_run_id=job.fetch_run_id,
                on_company_result=on_company_result,
            ),
            timeout=company_timeout_seconds(),
        )
        if on_log:
            on_log(msg)
        _finish_claimed_job(job, error=None)
        return new_count, False, True
    except FetchCancelled:
        _finish_claimed_job(job, error="cancelled")
        return 0, True, True
    except TimeoutError:
        limit = company_timeout_seconds()
        line = f"{name} — Error: timed out after {limit}s"
        if on_log:
            on_log(line)
        updated = _finish_claimed_job(job, error=line)
        return 0, False, bool(updated and updated.status != FetchJobStatus.QUEUED)
    except LookupError as exc:
        line = f"{name} — skipped ({exc})"
        if on_log:
            on_log(line)
        _finish_claimed_job(job, error=None)
        return 0, False, True
    except Exception as exc:
        line = f"{name} — Error: {exc}"
        if on_log:
            on_log(line)
        updated = _finish_claimed_job(job, error=str(exc))
        return 0, False, bool(updated and updated.status != FetchJobStatus.QUEUED)


async def _run_claimed_batch(
    client,
    jobs: list[FetchJob],
    *,
    workers: int,
    total: int,
    done_offset: int,
    on_progress,
    on_log,
    on_company_result,
) -> tuple[int, int, bool, set[str]]:
    slot = asyncio.Semaphore(workers)
    lock = asyncio.Lock()
    done = 0
    new_jobs_total = 0
    cancelled = False
    countries: set[str] = set()

    async def run_job(job: FetchJob) -> None:
        nonlocal done, new_jobs_total, cancelled
        async with slot:
            jobs_new, was_cancelled, settled = await _process_claimed_job(
                client,
                job,
                on_log=on_log,
                on_company_result=on_company_result,
            )
            async with lock:
                if was_cancelled:
                    cancelled = True
                    return
                new_jobs_total += jobs_new
                if not settled:
                    return
                done += 1
                countries.add(job.country)
                if on_progress:
                    on_progress({
                        "current": done_offset + done,
                        "total": total,
                        "company": job.company_name or "",
                        "status": "done",
                    })

    await asyncio.gather(*[run_job(job) for job in jobs])
    return new_jobs_total, done, cancelled, countries


async def drain_company_fetch_jobs(
    client,
    *,
    concurrency: int = 1,
    country: str | None = None,
    fetch_run_id: int | None = None,
    on_progress=None,
    on_log=None,
    on_company_result=None,
) -> tuple[int, int, bool, set[str]]:
    fetch_repo.reclaim_stale_claimed_fetch_jobs(stale_seconds=fetch_job_stale_seconds())
    workers = max(1, int(concurrency))
    worker_id = fetch_worker_id()
    new_jobs_total = 0
    done = 0
    cancelled = False
    countries: set[str] = set()
    total = fetch_repo.count_open_fetch_jobs(country=country, fetch_run_id=fetch_run_id)
    if on_progress:
        on_progress({
            "current": 0,
            "total": total,
            "company": None,
            "status": "starting",
        })

    while True:
        if fetch_run_id is not None and fetch_repo.fetch_run_cancel_requested(fetch_run_id):
            cancelled = True
            break
        claimed = fetch_repo.claim_fetch_jobs(
            worker_id=worker_id,
            limit=workers,
            country=country,
            fetch_run_id=fetch_run_id,
        )
        if claimed:
            batch_jobs, batch_done, batch_cancelled, batch_countries = await _run_claimed_batch(
                client,
                claimed,
                workers=workers,
                total=total,
                done_offset=done,
                on_progress=on_progress,
                on_log=on_log,
                on_company_result=on_company_result,
            )
            new_jobs_total += batch_jobs
            done += batch_done
            countries.update(batch_countries)
            if batch_cancelled:
                cancelled = True
                break
            continue
        open_count = fetch_repo.count_open_fetch_jobs(
            country=country,
            fetch_run_id=fetch_run_id,
        )
        if open_count == 0:
            break
        fetch_repo.reclaim_stale_claimed_fetch_jobs(stale_seconds=fetch_job_stale_seconds())
        await asyncio.sleep(0.05)

    if country:
        stamp_country_fetch_meta(country, new_jobs_total)
    if on_progress and not cancelled:
        on_progress({
            "current": done,
            "total": total,
            "company": None,
            "status": "done",
        })
    return new_jobs_total, done, cancelled, countries
