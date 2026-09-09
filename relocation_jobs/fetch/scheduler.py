from __future__ import annotations

import argparse
import logging
import os
import time

from relocation_jobs.core.ats_constants import HTTPX_AVAILABLE, MAX_CONCURRENCY
from relocation_jobs.core.log import configure_logging
from relocation_jobs.core.paths import supported_countries
from relocation_jobs.db import init_db
from relocation_jobs.users.repo import resolve_scheduler_user_id
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch import state as fetch_state
from relocation_jobs.fetch.runner import run_country_fetch_blocking
from relocation_jobs.fetch.listing_check import run_listing_check_cycle
from relocation_jobs.fetch.timeouts import country_timeout_seconds
from relocation_jobs.scrape.aggregator_seeds import ensure_aggregator_seeds

LOGGER = logging.getLogger("relocation_jobs.fetch.scheduler")


def schedule_enabled() -> bool:
    return os.environ.get("FETCH_SCHEDULE_ENABLED", "0").lower() not in ("0", "false", "no")


def schedule_interval_hours() -> float:
    raw = (os.environ.get("FETCH_SCHEDULE_INTERVAL_HOURS") or "6").strip()
    try:
        return max(0.25, float(raw))
    except (TypeError, ValueError):
        return 6.0


def schedule_concurrency() -> int:
    raw = (os.environ.get("FETCH_SCHEDULE_CONCURRENCY") or "2").strip()
    try:
        return max(1, min(int(raw), MAX_CONCURRENCY))
    except (TypeError, ValueError):
        return 2


def schedule_countries() -> tuple[str, ...]:
    raw = (os.environ.get("FETCH_SCHEDULE_COUNTRIES") or "").strip()
    if not raw:
        return tuple(sorted(supported_countries()))
    countries: list[str] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key not in supported_countries():
            raise ValueError(f"Unknown country in FETCH_SCHEDULE_COUNTRIES: {key}")
        if key not in countries:
            countries.append(key)
    if not countries:
        raise ValueError("FETCH_SCHEDULE_COUNTRIES is empty")
    return tuple(countries)


def bootstrap_scheduler() -> None:
    init_db()
    configure_logging()
    fetch_repo.reap_orphan_running_fetch_runs()
    ensure_aggregator_seeds()


def run_fetch_cycle(*, user_id: int | None = None) -> dict:
    if not schedule_enabled():
        return {"skipped": True, "reason": "schedule_disabled"}

    if not HTTPX_AVAILABLE:
        log_event("Scheduled fetch skipped: httpx is not installed", level=logging.ERROR)
        return {"skipped": True, "reason": "httpx_missing"}

    if fetch_state.fetch_is_running():
        log_event("Scheduled fetch skipped: another fetch is already running")
        return {"skipped": True, "reason": "fetch_busy"}

    resolved_user_id = user_id if user_id is not None else resolve_scheduler_user_id()
    countries = schedule_countries()
    concurrency = schedule_concurrency()
    started: list[str] = []
    skipped: list[str] = []

    log_event(
        "Scheduled fetch cycle starting",
        user_id=resolved_user_id,
        concurrency=concurrency,
        total=len(countries),
    )

    for country in countries:
        if fetch_state.fetch_is_running():
            skipped.extend(countries[countries.index(country):])
            log_event(
                "Scheduled fetch stopped: fetch became busy",
                country=country,
            )
            break

        try:
            run_id = run_country_fetch_blocking(
                user_id=resolved_user_id,
                country_key=country,
                concurrency=concurrency,
                timeout=country_timeout_seconds(),
            )
        except RuntimeError as exc:
            skipped.append(country)
            log_event(
                f"Scheduled fetch could not start for {country}: {exc}",
                country=country,
                level=logging.WARNING,
            )
            continue
        except TimeoutError:
            skipped.append(country)
            log_event(
                "Scheduled country fetch timed out",
                country=country,
                level=logging.ERROR,
            )
            fetch_state.abandon_fetch_after_timeout(
                result_line=f"Country fetch timed out after {country_timeout_seconds()}s",
            )
            continue

        started.append(country)
        log_event(
            "Scheduled country fetch finished",
            run_id=run_id,
            country=country,
            user_id=resolved_user_id,
            concurrency=concurrency,
        )

    result = {
        "skipped": False,
        "started": started,
        "not_started": skipped,
        "countries": list(countries),
        "concurrency": concurrency,
    }
    log_event(
        "Scheduled fetch cycle finished",
        total=len(countries),
    )
    return result


def _run_listing_check() -> dict:
    try:
        result = run_listing_check_cycle()
    except Exception as exc:
        log_event(f"Listing check failed: {exc}", level=logging.ERROR)
        return {"skipped": True, "reason": "error", "probed": 0, "closed": 0, "unknown": 0}
    log_event(
        "Listing check finished",
        probed=result.get("probed"),
        closed=result.get("closed"),
        unknown=result.get("unknown"),
        skipped=result.get("skipped"),
    )
    return result


def run_scheduled_pass(*, user_id: int | None = None) -> dict:
    listing_check = _run_listing_check()
    result = run_fetch_cycle(user_id=user_id)
    return {**result, "listing_check": listing_check}


def run_scheduler_loop() -> None:
    bootstrap_scheduler()
    if not schedule_enabled():
        LOGGER.error("FETCH_SCHEDULE_ENABLED is off; scheduler exiting")
        return

    interval_seconds = schedule_interval_hours() * 3600
    log_event(
        "Fetch scheduler started",
        concurrency=schedule_concurrency(),
        total=len(schedule_countries()),
    )

    while True:
        try:
            run_scheduled_pass()
        except Exception as exc:
            log_event(f"Scheduled fetch cycle failed: {exc}", level=logging.ERROR)
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scheduled country job fetches.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single fetch cycle and exit.",
    )
    args = parser.parse_args()

    if args.once:
        bootstrap_scheduler()
        if not schedule_enabled():
            LOGGER.error("FETCH_SCHEDULE_ENABLED is off")
            return 1
        print(run_scheduled_pass())
        return 0

    run_scheduler_loop()
    return 0
