from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from relocation_jobs.core.panel_flags import fetch_process_may_reap_orphans
from relocation_jobs.fetch import repo as fetch_repo

_EMPTY_REVIEW = {"included": [], "filtered": []}


@dataclass
class _Owner:
    run_id: int | None = None
    thread: threading.Thread | None = None
    last_row: dict | None = None


_lock = threading.RLock()
_owner = _Owner()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def idle_fetch_status() -> dict:
    return {
        "running": False,
        "run_id": None,
        "country": None,
        "company": None,
        "ats_type": None,
        "file": None,
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "concurrency": None,
        "result_line": None,
        "cancel_requested": False,
        "cancelled": False,
        "progress": {},
        "activity": {},
        "activity_log": [],
        "log": [],
        "review_jobs": None,
        "new_jobs_total": 0,
        "last_fetch_run": None,
    }


def status_from_row(row: dict | None) -> dict:
    status = idle_fetch_status()
    if not row:
        return status
    running = row.get("status") == "running"
    status.update({
        "running": running,
        "run_id": row.get("id"),
        "country": row.get("country"),
        "company": row.get("company_name"),
        "ats_type": row.get("ats_type"),
        "file": row.get("file"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "exit_code": row.get("exit_code"),
        "concurrency": row.get("concurrency"),
        "result_line": row.get("result_line"),
        "cancel_requested": bool(row.get("cancel_requested")),
        "cancelled": bool(row.get("cancelled")),
        "progress": dict(row.get("progress") or {}),
        "activity": dict(row.get("activity") or {}),
        "activity_log": list(row.get("activity_log") or []),
        "log": list(row.get("log") or []),
        "review_jobs": row.get("review_jobs"),
        "new_jobs_total": int(row.get("new_jobs") or 0),
        "last_fetch_run": None if running else row,
    })
    return status


def _owns(run_id: int) -> bool:
    return _owner.run_id is not None and int(_owner.run_id) == int(run_id)


def _running_row(run_id: int) -> dict | None:
    row = fetch_repo.get_running_fetch_run()
    if not row or int(row["id"]) != int(run_id):
        return None
    return row


def _live_row(run_id: int) -> dict | None:
    if not _owns(run_id):
        return None
    return _running_row(run_id)


def build_fetch_status() -> dict:
    reap_zombie_fetch()
    row = fetch_repo.get_running_fetch_run()
    if row:
        return status_from_row(row)
    with _lock:
        if _owner.last_row:
            return status_from_row(_owner.last_row)
    return idle_fetch_status()


def fetch_is_running() -> bool:
    reap_zombie_fetch()
    with _lock:
        if _owner.run_id is not None:
            if _owner.thread is None or _owner.thread.is_alive():
                return True
    return fetch_repo.get_running_fetch_run() is not None


def guard_fetch_start() -> bool:
    return not fetch_is_running()


def reset_for_run(
    *,
    user_id: int,
    country: str,
    file_name: str,
    concurrency: int,
    company: str | None = None,
    ats_type: str | None = None,
) -> int:
    row = fetch_repo.create_fetch_run(
        user_id=user_id,
        country=country,
        company_name=company,
        file_name=file_name,
        concurrency=concurrency,
        ats_type=ats_type,
        started_at=utc_now(),
    )
    run_id = int(row["id"])
    with _lock:
        _owner.run_id = run_id
        _owner.thread = None
        _owner.last_row = None
    return run_id


def set_fetch_thread(thread: threading.Thread | None) -> None:
    with _lock:
        _owner.thread = thread


def reap_zombie_fetch() -> None:
    with _lock:
        run_id = _owner.run_id
        thread = _owner.thread
    if run_id is not None:
        if thread is None:
            return
        if thread.is_alive():
            return
        append_log(run_id, "Fetch thread stopped unexpectedly")
        finish_run(run_id, exit_code=1, cancelled=False, result_line="Fetch thread stopped unexpectedly")
    if fetch_process_may_reap_orphans():
        with _lock:
            if _owner.run_id is not None:
                return
        fetch_repo.reap_orphan_running_fetch_runs()


def request_fetch_cancel() -> tuple[bool, str | None]:
    with _lock:
        run_id = _owner.run_id
    if run_id is None:
        row = fetch_repo.get_running_fetch_run()
        if not row:
            return False, "No fetch is running"
        fetch_repo.request_fetch_run_cancel(int(row["id"]))
        return True, None
    fetch_repo.request_fetch_run_cancel(int(run_id))
    return True, None


def abandon_fetch_after_timeout(*, result_line: str) -> None:
    request_fetch_cancel()
    with _lock:
        run_id = _owner.run_id
    if run_id:
        append_log(run_id, result_line)
        finish_run(run_id, exit_code=1, cancelled=False, result_line=result_line)
    set_fetch_thread(None)


def update_progress(run_id: int, progress: dict) -> None:
    with _lock:
        row = _live_row(run_id)
        if row is None:
            return
        prev = dict(row.get("progress") or {})
        merged = dict(progress)
        company_results = prev.get("company_results") or progress.get("company_results") or []
        if company_results:
            merged["company_results"] = list(company_results)
        fetch_repo.update_fetch_run_live(int(run_id), progress=merged)


def record_company_result(run_id: int, company_name: str, new_count: int, jobs: list[dict]) -> None:
    if new_count <= 0:
        return
    with _lock:
        row = _live_row(run_id)
        if row is None:
            return
        progress = dict(row.get("progress") or {})
        results = list(progress.get("company_results") or [])
        results.append({
            "company": company_name,
            "new_count": int(new_count),
            "jobs": list(jobs or []),
        })
        progress["company_results"] = results
        new_jobs = int(row.get("new_jobs") or 0) + int(new_count)
        fetch_repo.update_fetch_run_live(int(run_id), progress=progress, new_jobs=new_jobs)


def append_log(run_id: int, line: str) -> None:
    with _lock:
        row = _live_row(run_id)
        if row is None:
            return
        log = list(row.get("log") or [])
        log.append(line)
        fetch_repo.update_fetch_run_live(int(run_id), log=log)


def set_review_jobs(run_id: int, payload: dict) -> None:
    with _lock:
        if _live_row(run_id) is None:
            return
        fetch_repo.update_fetch_run_live(int(run_id), review_jobs=payload)


def ensure_review_jobs(run_id: int) -> None:
    with _lock:
        row = _live_row(run_id)
        if row is None or row.get("review_jobs") is not None:
            return
        fetch_repo.update_fetch_run_live(int(run_id), review_jobs=dict(_EMPTY_REVIEW))


def finish_run(
    run_id: int,
    *,
    exit_code: int,
    cancelled: bool,
    new_jobs: int = 0,
    companies_done: int | None = None,
    result_line: str | None = None,
) -> None:
    if not fetch_repo.fetch_run_is_running(int(run_id)):
        with _lock:
            if _owns(run_id):
                _owner.run_id = None
        return
    row = _running_row(run_id) or fetch_repo.get_running_fetch_run()
    progress = dict((row or {}).get("progress") or {})
    total = int(progress.get("total") or 0)
    if not cancelled:
        current = total if exit_code == 0 and total > 0 else int(companies_done or 0)
        progress = {**progress, "current": current, "status": "done"}
        if companies_done is None:
            companies_done = current
    finalized = fetch_repo.finalize_fetch_run(
        int(run_id),
        finished_at=utc_now(),
        exit_code=exit_code,
        cancelled=cancelled,
        new_jobs=new_jobs,
        companies_done=companies_done,
        companies_total=int(progress.get("total") or 0) or None,
        result_line=result_line,
        progress=progress,
        log=list((row or {}).get("log") or []),
        review_jobs=(row or {}).get("review_jobs"),
    )
    with _lock:
        if _owns(run_id):
            _owner.run_id = None
            _owner.thread = None
            _owner.last_row = finalized


def fetch_lock():
    return _lock


def reset_for_tests() -> None:
    with _lock:
        _owner.run_id = None
        _owner.thread = None
        _owner.last_row = None
