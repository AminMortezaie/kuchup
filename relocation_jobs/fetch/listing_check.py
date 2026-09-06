from __future__ import annotations

import asyncio
import os

from relocation_jobs.catalog.repo import (
    apply_listing_check_results,
    list_open_jobs_for_listing_check,
)
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.fetch.client import make_fetch_client
from relocation_jobs.scrape.listing_status import (
    ListingStatus,
    next_listing_check_state,
    probe_listing,
)
from relocation_jobs.scrape.merge import now_iso

DEFAULT_LIMIT = 200
DEFAULT_CONCURRENCY = 2
DEFAULT_MISSES = 2


def listing_check_enabled() -> bool:
    raw = (os.environ.get("FETCH_LISTING_CHECK_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no")


def listing_check_limit() -> int:
    raw = (os.environ.get("FETCH_LISTING_CHECK_LIMIT") or str(DEFAULT_LIMIT)).strip()
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def listing_check_concurrency() -> int:
    raw = (os.environ.get("FETCH_LISTING_CHECK_CONCURRENCY") or str(DEFAULT_CONCURRENCY)).strip()
    try:
        return max(1, min(int(raw), MAX_CONCURRENCY))
    except (TypeError, ValueError):
        return DEFAULT_CONCURRENCY


def listing_check_misses() -> int:
    raw = (os.environ.get("FETCH_LISTING_CHECK_MISSES") or str(DEFAULT_MISSES)).strip()
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MISSES


def _empty_result(*, skipped: bool = False, reason: str = "") -> dict:
    out = {"skipped": skipped, "probed": 0, "closed": 0, "unknown": 0, "open": 0}
    if reason:
        out["reason"] = reason
    return out


async def check_open_listings(
    client,
    *,
    limit: int | None = None,
    concurrency: int | None = None,
    threshold: int | None = None,
) -> dict:
    cap = listing_check_limit() if limit is None else max(0, int(limit))
    workers = listing_check_concurrency() if concurrency is None else max(1, int(concurrency))
    misses_needed = listing_check_misses() if threshold is None else max(1, int(threshold))
    jobs = list_open_jobs_for_listing_check(cap)
    if not jobs:
        return _empty_result()

    sem = asyncio.Semaphore(workers)
    seen_at = now_iso()
    updates: list[dict] = []
    closed = 0
    unknown = 0
    opened = 0

    async def one(job: dict) -> tuple[dict, ListingStatus]:
        async with sem:
            status = await probe_listing(client, job.get("url") or "", job.get("ats_type"))
        return job, status

    results = await asyncio.gather(*(one(job) for job in jobs))
    for job, status in results:
        next_misses, next_closed = next_listing_check_state(
            int(job.get("listing_misses") or 0),
            status,
            closed_at=job.get("closed_at") or "",
            now=seen_at,
            threshold=misses_needed,
        )
        if status is ListingStatus.UNKNOWN:
            unknown += 1
        elif status is ListingStatus.OPEN:
            opened += 1
        if next_misses == int(job.get("listing_misses") or 0) and next_closed == (job.get("closed_at") or ""):
            continue
        newly_closed = bool(next_closed) and not (job.get("closed_at") or "").strip()
        if newly_closed:
            closed += 1
        updates.append({
            "id": int(job["id"]),
            "listing_misses": next_misses,
            "closed_at": next_closed,
            "country": job.get("country") or "",
        })
    apply_listing_check_results(updates)
    return {
        "skipped": False,
        "probed": len(jobs),
        "closed": closed,
        "unknown": unknown,
        "open": opened,
    }


def run_listing_check_cycle() -> dict:
    if not listing_check_enabled():
        return _empty_result(skipped=True, reason="disabled")
    async def _run() -> dict:
        async with make_fetch_client(concurrency=listing_check_concurrency()) as client:
            return await check_open_listings(client)

    return asyncio.run(_run())
