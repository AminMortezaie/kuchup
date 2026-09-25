from __future__ import annotations

import asyncio
import logging
import os
import time

from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.log import configure_logging
from relocation_jobs.db import init_db
from relocation_jobs.fetch import go_results
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.fetch import service as fetch_service
from relocation_jobs.scrape.company import _mark_fetch_failed, process_company
from relocation_jobs.scrape.enrich import enrich_jobs

LOGGER = logging.getLogger("relocation_jobs.fetch.merge_consumer")


def poll_interval_seconds() -> float:
    raw = (os.environ.get("FETCH_MERGE_POLL_SECONDS") or "2").strip()
    try:
        return max(0.5, float(raw))
    except (TypeError, ValueError):
        return 2.0


async def _merge_ok_or_empty(row: dict) -> None:
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
        async with make_fetch_client(concurrency=MAX_CONCURRENCY) as client:
            msg, new_count = await process_company(
                client,
                company,
                1,
                1,
                fetch_board=fetch_board,
                enrich_board=enrich_jobs,
                sync_board=persist_board,
                enrich_concurrency=MAX_CONCURRENCY,
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


async def process_pending_row(row: dict) -> None:
    status = (row.get("status") or "").strip().lower()
    if status == "error":
        _merge_error(row)
        return
    if status in ("ok", "empty"):
        await _merge_ok_or_empty(row)
        return
    raise ValueError(f"Unknown fetch result status: {status}")


async def run_merge_pass(*, limit: int = 20) -> int:
    rows = go_results.list_pending_http_results(limit=limit)
    processed = 0
    for row in rows:
        await process_pending_row(row)
        go_results.mark_http_result_processed(int(row["id"]))
        processed += 1
        run_id = int(row["fetch_run_id"])
        if go_results.run_merge_complete(run_id):
            country = (row.get("country_key") or "").strip().lower()
            if country:
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
