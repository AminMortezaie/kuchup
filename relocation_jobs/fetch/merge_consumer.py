from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time

from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.log import configure_logging
from relocation_jobs.core.db import release_thread_connection
from relocation_jobs.db import init_db
from relocation_jobs.fetch import go_results
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.fetch import service as fetch_service
from relocation_jobs.roles.match import job_is_default_match
from relocation_jobs.roles.service import annotate_listings, default_keyword_lists
from relocation_jobs.scrape.company import _mark_fetch_failed, process_company
from relocation_jobs.scrape.enrich import enrich_jobs
from relocation_jobs.scrape.filter import filter_relevant_jobs

LOGGER = logging.getLogger("relocation_jobs.fetch.merge_consumer")


def poll_interval_seconds() -> float:
    raw = (os.environ.get("FETCH_MERGE_POLL_SECONDS") or "2").strip()
    try:
        return max(0.5, float(raw))
    except (TypeError, ValueError):
        return 2.0


async def _merge_ok_or_empty(
    row: dict,
    client,
    *,
    enrich_concurrency: int,
) -> None:
    country_key = (row.get("country_key") or "").strip().lower()
    name = (row.get("name") or "").strip()
    company = get_company(country_key, name)
    if company is None:
        raise LookupError(f"Company not found: {name}")

    raw_jobs = list(row.get("jobs") or [])

    def persist_board() -> None:
        sync_company_board_to_catalog(country_key, company)

    async def fetch_board(_client, _company, **_kwargs) -> list[dict]:
        return raw_jobs

    attempt_id = fetch_service.start_company_attempt(
        company,
        country_key=country_key,
        fetch_run_id=int(row["fetch_run_id"]),
    )
    try:
        msg, new_count = await process_company(
            client,
            company,
            1,
            1,
            fetch_board=fetch_board,
            enrich_board=enrich_jobs,
            sync_board=persist_board,
            enrich_concurrency=enrich_concurrency,
            catalog_country=country_key,
        )
    except Exception as exc:
        fetch_service.finish_company_attempt(
            attempt_id,
            company,
            f"Error: {exc}",
            0,
        )
        raise
    fetch_service.finish_company_attempt(attempt_id, company, msg, new_count)


def _merge_error(row: dict) -> None:
    country_key = (row.get("country_key") or "").strip().lower()
    name = (row.get("name") or "").strip()
    company = get_company(country_key, name)
    if company is None:
        raise LookupError(f"Company not found: {name}")
    _mark_fetch_failed(company)
    sync_company_board_to_catalog(country_key, company)
    attempt_id = fetch_service.start_company_attempt(
        company,
        country_key=country_key,
        fetch_run_id=int(row["fetch_run_id"]),
    )
    err = (row.get("error") or "fetch failed").strip()
    fetch_service.finish_company_attempt(
        attempt_id,
        company,
        f"Error: {err}",
        0,
    )


async def process_pending_row(
    row: dict,
    client=None,
    *,
    enrich_concurrency: int = 4,
) -> None:
    status = (row.get("status") or "").strip().lower()
    if status == "error":
        _merge_error(row)
        return
    if status in ("ok", "empty"):
        if client is None:
            async with make_fetch_client(concurrency=enrich_concurrency) as owned:
                await _merge_ok_or_empty(
                    row, owned, enrich_concurrency=enrich_concurrency,
                )
        else:
            await _merge_ok_or_empty(
                row, client, enrich_concurrency=enrich_concurrency,
            )
        return
    raise ValueError(f"Unknown fetch result status: {status}")


def matched_jobs_missing_text(jobs: list[dict]) -> list[dict]:
    includes, excludes = default_keyword_lists()
    listed = annotate_listings(filter_relevant_jobs(jobs, False), includes, excludes)
    return [
        job for job in listed
        if job_is_default_match(job)
        and (job.get("url") or "").strip()
        and not (job.get("description_text") or "").strip()
    ]


def prefetch_descriptions(rows: list[dict]) -> None:
    wanted: list[dict] = []
    for row in rows:
        if (row.get("status") or "").strip().lower() not in ("ok", "empty"):
            continue
        for job in matched_jobs_missing_text(list(row.get("jobs") or [])):
            wanted.append({
                "ats_type": row.get("ats_type") or "",
                "board_url": row.get("ats_url") or "",
                "url": job["url"],
            })
    if not wanted:
        return
    from relocation_jobs.fetch.runner import fetch_scheduler_bin

    proc = subprocess.run(
        [fetch_scheduler_bin(), "describe"],
        input=json.dumps(wanted),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        LOGGER.error("describe failed: %s", (proc.stderr or "").strip())
        return
    filled = {
        item.get("url"): item.get("description_text") or ""
        for item in json.loads(proc.stdout or "[]")
        if item.get("url")
    }
    for row in rows:
        for job in row.get("jobs") or []:
            text = (filled.get(job.get("url") or "") or "").strip()
            if text:
                job["description_text"] = text


def merge_ready_result(result_id: int) -> None:
    try:
        row = go_results.get_pending_http_result(int(result_id))
        if row is None:
            return
        prefetch_descriptions([row])
        asyncio.run(process_pending_row(row, enrich_concurrency=4))
        go_results.mark_http_result_processed(int(row["id"]))
    finally:
        release_thread_connection()


async def run_merge_pass(*, limit: int = 500, enqueue: bool = True) -> int:
    rows = go_results.list_pending_http_results(limit=limit)
    if not rows:
        return 0
    prefetch_descriptions(rows)
    workers = max(1, min(8, len(rows)))
    enrich_concurrency = max(1, min(4, workers))
    slot = asyncio.Semaphore(workers)
    processed = 0
    countries: dict[int, str] = {}

    def merge_one(row: dict) -> tuple[int, str]:
        try:
            asyncio.run(process_pending_row(row, enrich_concurrency=enrich_concurrency))
            go_results.mark_http_result_processed(int(row["id"]))
            run_id = int(row["fetch_run_id"])
            return run_id, (row.get("country_key") or "").strip().lower()
        finally:
            release_thread_connection()

    async def one(row: dict) -> None:
        nonlocal processed
        async with slot:
            run_id, country = await asyncio.to_thread(merge_one, row)
            processed += 1
            if country:
                countries[run_id] = country

    release_thread_connection()
    results = await asyncio.gather(*(one(row) for row in rows), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            LOGGER.error("merge row failed: %s", result)
    if enqueue:
        for run_id, country in countries.items():
            if go_results.run_merge_complete(run_id):
                enqueue_country_opportunity_refresh(country)
    return processed


def run_merge_loop() -> None:
    init_db()
    configure_logging()
    interval = poll_interval_seconds()
    LOGGER.info("HTTP fetch merge consumer started (poll=%ss)", interval)
    while True:
        try:
            processed = asyncio.run(run_merge_pass())
            if processed:
                LOGGER.info("merged %s fetch result(s)", processed)
        except Exception as exc:
            LOGGER.error("merge consumer pass failed: %s", exc)
        time.sleep(interval)


def main() -> int:
    run_merge_loop()
    return 0
