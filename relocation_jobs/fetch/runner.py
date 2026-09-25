from __future__ import annotations

import asyncio
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.paths import country_archive_filename
from relocation_jobs.core.scrape_cancel import FetchCancelled, clear_cancel_checker, set_cancel_checker
from relocation_jobs.core.db import release_thread_connection
from relocation_jobs.fetch import go_results
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch import state as fetch_state
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch.pipeline import fetch_and_persist_company
from relocation_jobs.fetch.timeouts import country_timeout_seconds


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def fetch_scheduler_bin() -> str:
    explicit = (os.environ.get("ATS_SCRAPE_BIN") or "").strip()
    if explicit:
        return explicit
    built = _repo_root() / "target" / "fetch-scheduler"
    if not built.is_file():
        built.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["go", "build", "-o", str(built), "./apps/ats-scrape"],
            cwd=_repo_root(),
            check=True,
        )
    return str(built)


def go_country_env(
    country_key: str,
    run_id: int,
    concurrency: int,
    ats_type: str | None,
    *,
    timeout: float | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["FETCH_SCHEDULE_ENABLED"] = "1"
    env["FETCH_SCHEDULE_COUNTRIES"] = country_key
    env["FETCH_HTTP_POOL_SIZE"] = str(max(1, min(int(concurrency), MAX_CONCURRENCY)))
    env["FETCH_RUN_ID"] = str(run_id)
    if ats_type:
        env["FETCH_ATS_TYPE"] = ats_type
    else:
        env.pop("FETCH_ATS_TYPE", None)
    limit = country_timeout_seconds() if timeout is None else int(timeout)
    env["FETCH_COUNTRY_TIMEOUT_SECONDS"] = str(max(60, limit))
    return env


def ready_result_id(line: str) -> int | None:
    parts = line.strip().split()
    if len(parts) != 2 or parts[0] != "FETCH_READY":
        return None
    try:
        result_id = int(parts[1])
    except ValueError:
        return None
    return result_id if result_id > 0 else None


def _go_country_fetch_worker(
    country_key: str,
    *,
    run_id: int,
    ats_type: str | None,
    concurrency: int = 1,
    timeout: float | None = None,
) -> None:
    from relocation_jobs.fetch.merge_consumer import merge_ready_result, run_merge_pass

    limit = country_timeout_seconds() if timeout is None else timeout

    def drain_merge() -> None:
        while asyncio.run(run_merge_pass(enqueue=False)) != 0:
            pass

    def fail(message: str) -> None:
        fetch_state.append_log(run_id, message)
        log_event(message)
        fetch_state.finish_run(
            run_id,
            exit_code=1,
            cancelled=False,
            new_jobs=0,
            companies_done=0,
            result_line=message,
        )

    proc = None
    timed_out = False
    try:
        proc = subprocess.Popen(
            [fetch_scheduler_bin(), "--once"],
            cwd=_repo_root(),
            env=go_country_env(
                country_key, run_id, concurrency, ats_type, timeout=timeout,
            ),
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def on_timeout() -> None:
            nonlocal timed_out
            timed_out = True
            proc.kill()

        timer = threading.Timer(limit, on_timeout)
        timer.start()
        pool = ThreadPoolExecutor(max_workers=8)
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                result_id = ready_result_id(line)
                if result_id is not None:
                    pool.submit(merge_ready_result, result_id)
            code = proc.wait()
        finally:
            timer.cancel()
            pool.shutdown(wait=True)
    except OSError as exc:
        fail(f"Error: {exc}")
        return
    drain_merge()
    release_thread_connection()
    if timed_out:
        fail(f"Error: timed out after {limit}s")
        return
    if code != 0:
        fail(f"Go fetch exited {code}")
        return
    if go_results.run_merge_complete(run_id):
        enqueue_country_opportunity_refresh(country_key)


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
        target=_go_country_fetch_worker,
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
    _go_country_fetch_worker(
        country_key,
        run_id=run_id,
        ats_type=None,
        concurrency=workers,
        timeout=limit,
    )
    return run_id
