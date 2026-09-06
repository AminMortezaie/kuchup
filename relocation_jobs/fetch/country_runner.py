from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from relocation_jobs.core.scrape_cancel import FetchCancelled, clear_cancel_checker, set_cancel_checker
from relocation_jobs.catalog.repo import (
    get_company,
    list_country_company_stubs,
    load_country_catalog,
    patch_country_catalog_meta,
)
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch.pipeline import fetch_and_persist_company
from relocation_jobs.fetch.timeouts import company_timeout_seconds
from relocation_jobs.async_jobs.enqueue import enqueue_country_opportunity_refresh
from relocation_jobs.scrape.aggregator_sync import should_skip_country_fetch
from relocation_jobs.scrape.merge import now_iso

OnProgress = Callable[[dict], None]
OnLog = Callable[[str], None]
OnCompanyResult = Callable[[str, int, list[dict]], None]


def _companies_to_fetch(
    country_key: str,
    *,
    skip_filled: bool,
    ats_type: str | None,
) -> list[dict]:
    companies = list_country_company_stubs(country_key)
    if not companies:
        raise LookupError(f"No catalog for country: {country_key}")
    companies = [c for c in companies if not should_skip_country_fetch(c.get("ats_type"))]
    if ats_type:
        want = ats_type.strip().lower()
        companies = [c for c in companies if (c.get("ats_type") or "").strip().lower() == want]
        if not companies:
            raise LookupError(f"No companies with ATS '{ats_type}' in {country_key}")
    if skip_filled:
        companies = [c for c in companies if not c.get("has_jobs")]
    return companies


def _cancel_checker(run_id: int) -> Callable[[], bool]:
    cache = {"at": 0.0, "value": False}

    def check() -> bool:
        now = time.monotonic()
        if now - cache["at"] < 1.0:
            return cache["value"]
        cache["value"] = fetch_repo.fetch_run_cancel_requested(run_id)
        cache["at"] = now
        return cache["value"]

    return check


def _emit_log(on_log: OnLog | None, line: str) -> None:
    if on_log:
        on_log(line)


async def _fetch_one_company(
    client,
    country_key: str,
    stub: dict,
    *,
    index: int,
    total: int,
    run_id: int,
    enrich_concurrency: int,
    slot: asyncio.Semaphore,
    on_log: OnLog | None,
    on_company_result: OnCompanyResult | None,
) -> tuple[int, bool]:
    name = stub.get("name") or ""
    async with slot:
        if fetch_repo.fetch_run_cancel_requested(run_id):
            return 0, True
        if get_company(country_key, name) is None:
            _emit_log(on_log, f"[{index}/{total}] {name} — skipped (not in catalog)")
            return 0, False
        try:
            msg, new_count = await asyncio.wait_for(
                fetch_and_persist_company(
                    client, country_key, name, fetch_run_id=run_id,
                    enrich_concurrency=enrich_concurrency,
                    on_company_result=on_company_result,
                    refresh_opportunities=False,
                ),
                timeout=company_timeout_seconds(),
            )
            _emit_log(on_log, msg)
            return new_count, False
        except FetchCancelled:
            return 0, True
        except TimeoutError:
            limit = company_timeout_seconds()
            _emit_log(on_log, f"[{index}/{total}] {name} — Error: timed out after {limit}s")
            return 0, False
        except Exception as exc:
            _emit_log(on_log, f"[{index}/{total}] {name} — Error: {exc}")
            return 0, False


async def _run_companies(
    client,
    country_key: str,
    companies: list[dict],
    *,
    run_id: int,
    workers: int,
    enrich_concurrency: int,
    on_progress: OnProgress | None,
    on_log: OnLog | None,
    on_company_result: OnCompanyResult | None,
) -> tuple[int, int, bool]:
    total = len(companies)
    slot = asyncio.Semaphore(workers)
    lock = asyncio.Lock()
    done = 0
    new_jobs_total = 0
    cancelled = False

    async def run_stub(index: int, stub: dict) -> None:
        nonlocal done, new_jobs_total, cancelled
        jobs, was_cancelled = await _fetch_one_company(
            client,
            country_key,
            stub,
            index=index,
            total=total,
            run_id=run_id,
            enrich_concurrency=enrich_concurrency,
            slot=slot,
            on_log=on_log,
            on_company_result=on_company_result,
        )
        async with lock:
            if was_cancelled:
                cancelled = True
                return
            new_jobs_total += jobs
            done += 1
            if on_progress:
                on_progress({
                    "current": done,
                    "total": total,
                    "company": stub.get("name") or "",
                    "status": "done",
                })

    await asyncio.gather(*[
        run_stub(index, stub)
        for index, stub in enumerate(companies, start=1)
    ])
    return new_jobs_total, done, cancelled


async def run_country_fetch(
    client,
    country_key: str,
    *,
    run_id: int,
    skip_filled: bool = False,
    ats_type: str | None = None,
    concurrency: int = 1,
    on_progress: OnProgress | None = None,
    on_log: OnLog | None = None,
    on_company_result: OnCompanyResult | None = None,
) -> tuple[int, int, bool]:
    companies = _companies_to_fetch(
        country_key,
        skip_filled=skip_filled,
        ats_type=ats_type,
    )
    total = len(companies)
    workers = max(1, min(concurrency, total))
    enrich_concurrency = max(1, min(4, workers))

    def report(current: int, company_name: str | None, status: str) -> None:
        if on_progress:
            on_progress({
                "current": current,
                "total": total,
                "company": company_name,
                "status": status,
            })

    set_cancel_checker(_cancel_checker(run_id))
    report(0, None, "starting")
    log_event(
        f"country fetch {country_key}: {total} companies, concurrency={workers}",
        enrich_concurrency=enrich_concurrency,
    )
    try:
        new_jobs_total, done, cancelled = await _run_companies(
            client,
            country_key,
            companies,
            run_id=run_id,
            workers=workers,
            enrich_concurrency=enrich_concurrency,
            on_progress=on_progress,
            on_log=on_log,
            on_company_result=on_company_result,
        )
    finally:
        clear_cancel_checker()

    ts = now_iso()
    refreshed = load_country_catalog(country_key) or {}
    patch_country_catalog_meta(
        country_key,
        updated=ts,
        jobs_fetched=ts,
        last_fetch_new_jobs=new_jobs_total,
        total=len(refreshed.get("companies") or []),
    )
    if not cancelled:
        report(done, None, "done")
    if done > 0:
        enqueue_country_opportunity_refresh(country_key)
    return new_jobs_total, done, cancelled
