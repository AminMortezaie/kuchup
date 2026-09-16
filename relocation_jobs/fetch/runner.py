from __future__ import annotations

import asyncio
import threading

from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.paths import country_archive_filename
from relocation_jobs.core.scrape_cancel import FetchCancelled, clear_cancel_checker, set_cancel_checker
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch import state as fetch_state
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.fetch.country_runner import run_country_fetch
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch.pipeline import fetch_and_persist_company
from relocation_jobs.fetch.queue import drain_company_fetch_jobs, enqueue_country_company_jobs
from relocation_jobs.fetch.timeouts import country_timeout_seconds, fetch_job_stale_seconds


def _finish_lines(cancelled: bool, exit_code: int, *, done_line: str) -> tuple[str, str]:
    if cancelled:
        return "Cancelled by user", "Cancelled by user"
    if exit_code == 0:
        return done_line, "Finished (exit 0)"
    line = f"Finished (exit {exit_code})"
    return line, line


def _complete_run(
    run_id: int,
    *,
    exit_code: int,
    cancelled: bool,
    new_jobs: int,
    companies_done: int,
    done_line: str,
) -> None:
    result_line, log_line = _finish_lines(cancelled, exit_code, done_line=done_line)
    fetch_state.append_log(run_id, log_line)
    fetch_state.finish_run(
        run_id,
        exit_code=exit_code,
        cancelled=cancelled,
        new_jobs=new_jobs,
        companies_done=companies_done,
        result_line=result_line,
    )


def _country_fetch_worker(
    country_key: str,
    *,
    run_id: int,
    ats_type: str | None,
    concurrency: int = 1,
    timeout: float | None = None,
) -> None:
    exit_code = 1
    cancelled = False
    timed_out = False
    new_jobs_total = 0
    companies_done = 0

    def on_progress(progress: dict) -> None:
        fetch_state.update_progress(run_id, progress)

    def on_company_result(company_name: str, new_count: int, jobs: list[dict]) -> None:
        fetch_state.record_company_result(run_id, company_name, new_count, jobs)

    def append_log(line: str) -> None:
        fetch_state.append_log(run_id, line)
        log_event(line)

    try:
        async def _run():
            nonlocal new_jobs_total, companies_done, cancelled
            async with make_fetch_client(concurrency=concurrency) as client:
                coro = run_country_fetch(
                    client,
                    country_key,
                    run_id=run_id,
                    ats_type=ats_type,
                    concurrency=concurrency,
                    on_progress=on_progress,
                    on_log=append_log,
                    on_company_result=on_company_result,
                )
                if timeout is None:
                    return await coro
                return await asyncio.wait_for(coro, timeout=timeout)

        new_jobs_total, companies_done, cancelled = asyncio.run(_run())
        exit_code = 130 if cancelled else 0
    except TimeoutError:
        timed_out = True
        limit = timeout if timeout is not None else country_timeout_seconds()
        append_log(f"Error: timed out after {limit}s")
        exit_code = 1
    except Exception as exc:
        append_log(f"Error: {exc}")
        exit_code = 1
    finally:
        _complete_run(
            run_id,
            exit_code=exit_code,
            cancelled=cancelled,
            new_jobs=new_jobs_total,
            companies_done=companies_done,
            done_line=f"Done {companies_done} companies, {new_jobs_total} new jobs",
        )
    if timed_out:
        limit = timeout if timeout is not None else country_timeout_seconds()
        raise TimeoutError(f"Country fetch timed out after {limit}s")
    if exit_code == 0 and companies_done > 0:
        enqueue_country_opportunity_refresh(country_key)


def _queued_country_fetch_worker(
    country_key: str,
    *,
    run_id: int,
    user_id: int,
    ats_type: str | None,
    concurrency: int = 1,
    timeout: float | None = None,
) -> None:
    exit_code = 1
    cancelled = False
    timed_out = False
    new_jobs_total = 0
    companies_done = 0

    def on_progress(progress: dict) -> None:
        fetch_state.update_progress(run_id, progress)

    def on_company_result(company_name: str, new_count: int, jobs: list[dict]) -> None:
        fetch_state.record_company_result(run_id, company_name, new_count, jobs)

    def append_log(line: str) -> None:
        fetch_state.append_log(run_id, line)
        log_event(line)

    try:
        enqueue_country_company_jobs(
            country_key,
            fetch_run_id=run_id,
            user_id=user_id,
            ats_type=ats_type,
        )

        async def _run():
            nonlocal new_jobs_total, companies_done, cancelled
            async with make_fetch_client(concurrency=concurrency) as client:
                coro = drain_company_fetch_jobs(
                    client,
                    concurrency=concurrency,
                    country=country_key,
                    fetch_run_id=run_id,
                    on_progress=on_progress,
                    on_log=append_log,
                    on_company_result=on_company_result,
                )
                if timeout is None:
                    return await coro
                return await asyncio.wait_for(coro, timeout=timeout)

        new_jobs_total, companies_done, cancelled, _countries = asyncio.run(_run())
        exit_code = 130 if cancelled else 0
    except TimeoutError:
        timed_out = True
        limit = timeout if timeout is not None else country_timeout_seconds()
        append_log(f"Error: timed out after {limit}s")
        exit_code = 1
    except Exception as exc:
        append_log(f"Error: {exc}")
        exit_code = 1
    finally:
        _complete_run(
            run_id,
            exit_code=exit_code,
            cancelled=cancelled,
            new_jobs=new_jobs_total,
            companies_done=companies_done,
            done_line=f"Done {companies_done} companies, {new_jobs_total} new jobs",
        )
    if timed_out:
        limit = timeout if timeout is not None else country_timeout_seconds()
        raise TimeoutError(f"Country fetch timed out after {limit}s")
    if exit_code == 0 and companies_done > 0:
        enqueue_country_opportunity_refresh(country_key)


def recover_pending_fetch_jobs_blocking(*, concurrency: int = 1) -> dict:
    empty = {
        "new_jobs": 0,
        "done": 0,
        "cancelled": False,
        "countries": [],
    }
    fetch_repo.reclaim_stale_claimed_fetch_jobs(stale_seconds=fetch_job_stale_seconds())
    if fetch_repo.count_open_fetch_jobs() == 0:
        return empty

    async def _run():
        async with make_fetch_client(concurrency=concurrency) as client:
            return await drain_company_fetch_jobs(client, concurrency=concurrency)

    new_jobs_total, companies_done, cancelled, countries = asyncio.run(_run())
    if companies_done > 0:
        for country in sorted(countries):
            enqueue_country_opportunity_refresh(country)
    return {
        "new_jobs": new_jobs_total,
        "done": companies_done,
        "cancelled": cancelled,
        "countries": sorted(countries),
    }


def _begin_country_run(
    *,
    user_id: int,
    country_key: str,
    ats_type: str | None = None,
    concurrency: int = 1,
) -> tuple[int, int]:
    fetch_state.reap_zombie_fetch()
    workers = max(1, min(int(concurrency), MAX_CONCURRENCY))
    with fetch_state.fetch_lock():
        if fetch_state.fetch_is_running():
            raise RuntimeError("A fetch is already running")
        run_id = fetch_state.reset_for_run(
            user_id=user_id,
            country=country_key,
            file_name=country_archive_filename(country_key),
            concurrency=workers,
            ats_type=ats_type,
        )
    return run_id, workers


def _company_fetch_worker(
    country_key: str,
    company_name: str,
    *,
    run_id: int,
) -> None:
    exit_code = 1
    cancelled = False
    new_jobs_total = 0
    result_message = ""
    set_cancel_checker(lambda: fetch_repo.fetch_run_cancel_requested(run_id))
    try:
        fetch_state.update_progress(run_id, {
            "current": 0,
            "total": 1,
            "company": company_name,
            "status": "fetching",
        })
        fetch_state.append_log(run_id, f"Fetching {company_name}")
        log_event(f"Fetching {company_name}")

        async def _run() -> tuple[str, int]:
            async with make_fetch_client(concurrency=MAX_CONCURRENCY) as client:
                return await fetch_and_persist_company(
                    client,
                    country_key,
                    company_name,
                    fetch_run_id=run_id,
                    enrich_concurrency=MAX_CONCURRENCY,
                    review_mode=True,
                    on_review=lambda payload: fetch_state.set_review_jobs(run_id, payload),
                )

        result_message, new_jobs_total = asyncio.run(_run())
        fetch_state.append_log(run_id, result_message)
        log_event(result_message)
        if fetch_repo.fetch_run_cancel_requested(run_id):
            cancelled = True
            exit_code = 130
        else:
            exit_code = 0
    except FetchCancelled:
        cancelled = True
        exit_code = 130
    except Exception as exc:
        fetch_state.append_log(run_id, f"Error: {exc}")
        log_event(f"Error: {exc}")
        exit_code = 1
    finally:
        clear_cancel_checker()
        fetch_state.ensure_review_jobs(run_id)
        _complete_run(
            run_id,
            exit_code=exit_code,
            cancelled=cancelled,
            new_jobs=new_jobs_total,
            companies_done=1 if exit_code == 0 and not cancelled else 0,
            done_line=result_message or "Finished (exit 0)",
        )
    if exit_code == 0 and not cancelled:
        enqueue_country_opportunity_refresh(country_key)


def start_company_fetch(
    *,
    user_id: int,
    country_key: str,
    company_name: str,
) -> int:
    fetch_state.reap_zombie_fetch()
    with fetch_state.fetch_lock():
        if fetch_state.fetch_is_running():
            raise RuntimeError("A fetch is already running")
        run_id = fetch_state.reset_for_run(
            user_id=user_id,
            country=country_key,
            file_name=country_archive_filename(country_key),
            concurrency=1,
            company=company_name,
        )
        thread = threading.Thread(
            target=_company_fetch_worker,
            args=(country_key, company_name),
            kwargs={"run_id": run_id},
            daemon=True,
        )
        fetch_state.set_fetch_thread(thread)
    thread.start()
    return run_id


def start_country_fetch(
    *,
    user_id: int,
    country_key: str,
    ats_type: str | None = None,
    concurrency: int = 1,
) -> int:
    run_id, workers = _begin_country_run(
        user_id=user_id,
        country_key=country_key,
        ats_type=ats_type,
        concurrency=concurrency,
    )
    thread = threading.Thread(
        target=_country_fetch_worker,
        args=(country_key,),
        kwargs={
            "run_id": run_id,
            "ats_type": ats_type,
            "concurrency": workers,
        },
        daemon=True,
    )
    fetch_state.set_fetch_thread(thread)
    thread.start()
    return run_id


def run_country_fetch_blocking(
    *,
    user_id: int,
    country_key: str,
    concurrency: int = 1,
    timeout: float | None = None,
) -> int:
    run_id, workers = _begin_country_run(
        user_id=user_id,
        country_key=country_key,
        concurrency=concurrency,
    )
    limit = country_timeout_seconds() if timeout is None else timeout
    _queued_country_fetch_worker(
        country_key,
        run_id=run_id,
        user_id=user_id,
        ats_type=None,
        concurrency=workers,
        timeout=limit,
    )
    return run_id
