from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


def company_timeout_seconds() -> int:
    return _env_int("FETCH_COMPANY_TIMEOUT_SECONDS", 300)


def country_timeout_seconds() -> int:
    return _env_int("FETCH_COUNTRY_TIMEOUT_SECONDS", 2700)


def playwright_board_timeout_seconds() -> int:
    return _env_int("PLAYWRIGHT_BOARD_TIMEOUT_SECONDS", 90)


def fetch_job_max_attempts() -> int:
    return _env_int("FETCH_JOB_MAX_ATTEMPTS", 3)


def fetch_job_stale_seconds() -> int:
    return _env_int("FETCH_JOB_STALE_SECONDS", company_timeout_seconds() + 60)


def fetch_job_retry_seconds() -> int:
    raw = (os.environ.get("FETCH_JOB_RETRY_SECONDS") or "").strip()
    if not raw:
        return 60
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 60
