from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

_MODE_AUTO = "auto"
_MODE_GO = "go"
_MODE_PYTHON = "python"
_VALID_MODES = frozenset({_MODE_AUTO, _MODE_GO, _MODE_PYTHON})
_DEFAULT_BIN = "/usr/local/bin/ats-scrape"
_TIMEOUT_ENV = "ATS_SCRAPE_TIMEOUT_SECONDS"
_BIN_ENV = "ATS_SCRAPE_BIN"
_MODE_ENV = "FETCH_HTTP_SCRAPE"
_JOB_KEYS = ("title", "url", "location", "locations", "employer", "description_text")


class GoScrapeError(LookupError):
    pass


def http_scrape_mode() -> str:
    raw = (os.environ.get(_MODE_ENV) or _MODE_AUTO).strip().lower()
    if raw not in _VALID_MODES:
        raise ValueError(f"Unknown {_MODE_ENV}: {raw}")
    return raw


def scrape_binary() -> str:
    path, _reason = _resolve_binary()
    return path


def go_board_jobs(company: dict) -> list[dict] | None:
    mode = http_scrape_mode()
    if mode == _MODE_PYTHON:
        return None
    binary, reason = _resolve_binary()
    if not binary:
        if mode == _MODE_GO:
            raise GoScrapeError(reason)
        return None
    try:
        completed = subprocess.run(
            [binary],
            input=_request_payload(company),
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if mode == _MODE_GO:
            raise GoScrapeError("ats-scrape timed out") from exc
        return None
    if completed.returncode == 0:
        return _jobs_from_stdout(completed.stdout, strict=mode == _MODE_GO)
    if mode == _MODE_GO:
        detail = (completed.stderr or "").strip() or f"ats-scrape exited {completed.returncode}"
        raise GoScrapeError(detail)
    return None


def _resolve_binary() -> tuple[str, str]:
    explicit = (os.environ.get(_BIN_ENV) or "").strip()
    if explicit:
        if _executable(explicit):
            return explicit, ""
        return "", f"{_BIN_ENV} is not executable: {explicit}"
    if _executable(_DEFAULT_BIN):
        return _DEFAULT_BIN, ""
    return "", f"{_BIN_ENV} is not set"


def _executable(path: str) -> bool:
    candidate = Path(path)
    return candidate.is_file() and os.access(candidate, os.X_OK)


def _timeout_seconds() -> float:
    raw = (os.environ.get(_TIMEOUT_ENV) or "180").strip()
    try:
        return max(5.0, float(raw))
    except (TypeError, ValueError):
        return 180.0


def _request_payload(company: dict) -> str:
    return json.dumps({
        "ats_type": (company.get("ats_type") or "").strip().lower(),
        "ats_url": (company.get("ats_url") or "").strip(),
        "careers_url": (company.get("careers_url") or "").strip(),
        "name": (company.get("name") or "").strip(),
    })


def _jobs_from_stdout(stdout: str, *, strict: bool) -> list[dict] | None:
    try:
        payload = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        if strict:
            raise GoScrapeError("ats-scrape returned invalid JSON")
        return None
    if not isinstance(payload, list):
        if strict:
            raise GoScrapeError("ats-scrape returned invalid JSON")
        return None
    jobs: list[dict] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        job = _job_row(row)
        if job:
            jobs.append(job)
    return jobs


def _job_row(row: dict) -> dict:
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "").strip()
    if not title or not url:
        return {}
    job = {"title": title, "url": url}
    for key in _JOB_KEYS[2:]:
        value = row.get(key)
        if value:
            job[key] = value
    return job
