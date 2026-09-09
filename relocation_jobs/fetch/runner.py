from __future__ import annotations

import asyncio
import threading

from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.scrape_cancel import FetchCancelled, clear_cancel_checker, set_cancel_checker
from relocation_jobs.core.paths import country_archive_filename
from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch import state as fetch_state
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.fetch.country_runner import run_country_fetch
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch.pipeline import fetch_and_persist_company
from relocation_jobs.fetch.timeouts import country_timeout_seconds


def _append_log(line: str) -> None:
    fetch_state.append_log_line(line)
    log_event(line)


def _country_fetch_worker(
    country_key: str,
    *,
    run_id: int,
    skip_filled: bool,
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
        fetch_state.update_progress_for_run(run_id, progress)

    def on_company_result(company_name: str, new_count: int, jobs: list[dict]) -> None:
        fetch_state.record_company_result_for_run(run_id, company_name, new_count, jobs)

    def append_log(line: str) -> None:
        fetch_state.append_log_line_for_run(run_id, line)
        log_event(line)

    try:
        async def _run():
            nonlocal new_jobs_total, companies_done, cancelled
            async with make_fetch_client(concurrency=concurrency) as client:
                coro = run_country_fetch(
                    client,
                    country_key,
                    run_id=run_id,
                    skip_filled=skip_filled,
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
        if exit_code == 0 and companies_done > 0:
            enqueue_country_opportunity_refresh(country_key)
    except TimeoutError:
        timed_out = True
        limit = timeout if timeout is not None else country_timeout_seconds()
        append_log(f"Error: timed out after {limit}s")
        exit_code = 1
    except Exception as exc:
        append_log(f"Error: {exc}")
        exit_code = 1
    finally:
        finish_line = None

        def _finish(st: dict) -> None:
            nonlocal finish_line
            if cancelled:
                st["cancelled"] = True
                st["exit_code"] = 130
                finish_line = "Cancelled by user"
            else:
                st["exit_code"] = exit_code
                finish_line = "Finished (exit 0)" if exit_code == 0 else f"Finished (exit {exit_code})"
            st["new_jobs_total"] = new_jobs_total
            prog = dict(st.get("progress") or {})
            total = int(prog.get("total") or 0)
            if not cancelled:
                current = total if exit_code == 0 and total > 0 else companies_done
                st["progress"] = {**prog, "current": current, "status": "done"}
            if finish_line:
                st["log"].append(finish_line)
            st["result_line"] = (
                f"Done {companies_done} companies, {new_jobs_total} new jobs"
                if exit_code == 0
                else finish_line
            )
            st["running"] = False
            st["finished_at"] = fetch_state.utc_now()

        fetch_state.mutate_state_for_run(run_id, _finish)
        fetch_state.sync_live_to_db()
        fetch_state.persist_fetch_run(run_id)
    if timed_out:
        limit = timeout if timeout is not None else country_timeout_seconds()
        raise TimeoutError(f"Country fetch timed out after {limit}s")


def _begin_country_run(
    *,
    user_id: int,
    country_key: str,
    ats_type: str | None = None,
    concurrency: int = 1,
) -> tuple[int, int]:
    fetch_state.reap_zombie_fetch()
    if fetch_state.fetch_is_running():
        raise RuntimeError("A fetch is already running")
    workers = max(1, min(int(concurrency), MAX_CONCURRENCY))
    file_name = country_archive_filename(country_key)
    with fetch_state.fetch_lock():
        run_id = fetch_state.reset_for_run(
            user_id=user_id,
            country=country_key,
            file_name=file_name,
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
        fetch_state.mutate_state_for_run(run_id, lambda st: st.update({
            "progress": {
                "current": 0,
                "total": 1,
                "company": company_name,
                "status": "fetching",
            },
        }))
        fetch_state.sync_live_to_db()
        _append_log(f"Fetching {company_name}")

        async def _run() -> tuple[str, int]:
            async with make_fetch_client(concurrency=MAX_CONCURRENCY) as client:
                return await fetch_and_persist_company(
                    client,
                    country_key,
                    company_name,
                    fetch_run_id=run_id,
                    enrich_concurrency=MAX_CONCURRENCY,
                    review_mode=True,
                    on_review=fetch_state.set_review_jobs,
                )

        result_message, new_jobs_total = asyncio.run(_run())
        _append_log(result_message)
        if fetch_repo.fetch_run_cancel_requested(run_id):
            cancelled = True
            exit_code = 130
        else:
            exit_code = 0
            enqueue_country_opportunity_refresh(country_key)
    except FetchCancelled:
        cancelled = True
        exit_code = 130
    except Exception as exc:
        _append_log(f"Error: {exc}")
        exit_code = 1
    finally:
        clear_cancel_checker()
        finish_line = None

        def _finish(st: dict) -> None:
            nonlocal finish_line
            if cancelled:
                st["cancelled"] = True
                st["exit_code"] = 130
                finish_line = "Cancelled by user"
            else:
                st["exit_code"] = exit_code
                finish_line = "Finished (exit 0)" if exit_code == 0 else f"Finished (exit {exit_code})"
            st["new_jobs_total"] = new_jobs_total
            if exit_code == 0 and not cancelled:
                st["progress"] = {
                    "current": 1,
                    "total": 1,
                    "company": company_name,
                    "status": "done",
                }
            if st.get("review_jobs") is None:
                st["review_jobs"] = {"included": [], "filtered": []}
            if finish_line:
                st["log"].append(finish_line)
            st["result_line"] = (
                result_message
                if exit_code == 0 and result_message
                else finish_line
            )
            st["running"] = False
            st["finished_at"] = fetch_state.utc_now()

        fetch_state.mutate_state_for_run(run_id, _finish)
        fetch_state.sync_live_to_db()
        fetch_state.persist_fetch_run(run_id)


def start_company_fetch(
    *,
    user_id: int,
    country_key: str,
    company_name: str,
) -> int:
    fetch_state.reap_zombie_fetch()
    if fetch_state.fetch_is_running():
        raise RuntimeError("A fetch is already running")
    file_name = country_archive_filename(country_key)
    with fetch_state.fetch_lock():
        run_id = fetch_state.reset_for_run(
            user_id=user_id,
            country=country_key,
            file_name=file_name,
            concurrency=1,
            company=company_name,
        )
        fetch_state.mutate_state(lambda st: st.update({
            "progress": {
                "current": 0,
                "total": 1,
                "company": company_name,
                "status": "starting",
            },
        }))
        thread = threading.Thread(
            target=_company_fetch_worker,
            args=(country_key, company_name),
            kwargs={"run_id": run_id},
            daemon=True,
        )
        fetch_state.set_fetch_thread(thread)
    fetch_state.sync_live_to_db()
    thread.start()
    return run_id


def start_country_fetch(
    *,
    user_id: int,
    country_key: str,
    skip_filled: bool = False,
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
            "skip_filled": skip_filled,
            "ats_type": ats_type,
            "concurrency": workers,
        },
        daemon=True,
    )
    with fetch_state.fetch_lock():
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
    _country_fetch_worker(
        country_key,
        run_id=run_id,
        skip_filled=False,
        ats_type=None,
        concurrency=workers,
        timeout=limit,
    )
    return run_id


async def run_single_company_fetch_async(
    country_key: str,
    company_name: str,
    *,
    fetch_run_id: int | None = None,
) -> tuple[str, int]:
    async with make_fetch_client(concurrency=MAX_CONCURRENCY) as client:
        return await fetch_and_persist_company(
            client,
            country_key,
            company_name,
            fetch_run_id=fetch_run_id,
        )
