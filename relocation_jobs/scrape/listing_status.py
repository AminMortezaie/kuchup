from __future__ import annotations

import json
import re
from collections.abc import Callable
from enum import Enum

import httpx

from relocation_jobs.scrape.boards.ashby import ashby_job_board_api_url, ashby_job_ids_from_url
from relocation_jobs.scrape.boards.greenhouse import (
    greenhouse_job_detail_api_url,
    greenhouse_job_ids_from_url,
)

CLOSED_PHRASES = (
    "no longer available",
    "position has been filled",
    "job not found",
)

_LEVER_POSTING_RE = re.compile(r"lever\.co/[^/]+/([0-9a-f-]{36})", re.I)

_PROBE_TIMEOUT = 10.0


class ListingStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


def classify_http_result(status: int, body: str) -> ListingStatus:
    if status in (404, 410):
        return ListingStatus.CLOSED
    if status != 200:
        return ListingStatus.UNKNOWN
    text = (body or "").strip()
    if not text:
        return ListingStatus.UNKNOWN
    lowered = text.lower()
    if any(phrase in lowered for phrase in CLOSED_PHRASES):
        return ListingStatus.CLOSED
    return ListingStatus.OPEN


def next_listing_check_state(
    misses: int,
    status: ListingStatus,
    *,
    closed_at: str,
    now: str,
    threshold: int,
) -> tuple[int, str]:
    current = max(0, int(misses or 0))
    if status is ListingStatus.UNKNOWN:
        return current, (closed_at or "").strip()
    if status is ListingStatus.OPEN:
        return 0, (closed_at or "").strip()
    updated = current + 1
    existing = (closed_at or "").strip()
    if updated >= threshold and not existing:
        return updated, now
    return updated, existing


def _lever_posting_api_url(url: str) -> str | None:
    match = _LEVER_POSTING_RE.search(url or "")
    if not match:
        return None
    return f"https://api.lever.co/v0/postings/{match.group(1)}"


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    try:
        return await client.get(url, timeout=_PROBE_TIMEOUT)
    except httpx.HTTPError:
        return None


def _json_payload(response: httpx.Response) -> dict | None:
    try:
        data = response.json()
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def _probe_greenhouse(client: httpx.AsyncClient, url: str) -> ListingStatus:
    ids = greenhouse_job_ids_from_url(url)
    if not ids:
        return await _probe_generic(client, url)
    slug, job_id = ids
    first = await _get(client, greenhouse_job_detail_api_url(slug, job_id, eu=False))
    if first is None:
        return ListingStatus.UNKNOWN
    status = _classify_greenhouse_response(first)
    if status is ListingStatus.OPEN:
        return status
    if status is ListingStatus.UNKNOWN:
        return status
    second = await _get(client, greenhouse_job_detail_api_url(slug, job_id, eu=True))
    if second is None:
        return ListingStatus.UNKNOWN
    eu_status = _classify_greenhouse_response(second)
    if eu_status is ListingStatus.OPEN:
        return ListingStatus.OPEN
    if eu_status is ListingStatus.UNKNOWN:
        return ListingStatus.UNKNOWN
    return ListingStatus.CLOSED


def _classify_greenhouse_response(response: httpx.Response) -> ListingStatus:
    if response.status_code in (404, 410):
        return ListingStatus.CLOSED
    if response.status_code != 200:
        return classify_http_result(response.status_code, response.text)
    payload = _json_payload(response)
    if payload is None:
        return classify_http_result(200, response.text)
    content = (payload.get("content") or "").strip()
    return classify_http_result(200, content)


async def _probe_lever(client: httpx.AsyncClient, url: str) -> ListingStatus:
    api = _lever_posting_api_url(url)
    if not api:
        return await _probe_generic(client, url)
    response = await _get(client, api)
    if response is None:
        return ListingStatus.UNKNOWN
    if response.status_code in (404, 410):
        return ListingStatus.CLOSED
    if response.status_code != 200:
        return classify_http_result(response.status_code, response.text)
    payload = _json_payload(response)
    if payload is None:
        return classify_http_result(200, response.text)
    text = (payload.get("descriptionPlain") or payload.get("description") or "").strip()
    return classify_http_result(200, text)


async def _probe_ashby(client: httpx.AsyncClient, url: str) -> ListingStatus:
    ids = ashby_job_ids_from_url(url)
    if not ids:
        return await _probe_generic(client, url)
    slug, job_id = ids
    response = await _get(client, ashby_job_board_api_url(slug))
    if response is None:
        return ListingStatus.UNKNOWN
    if response.status_code != 200:
        return classify_http_result(response.status_code, response.text)
    payload = _json_payload(response)
    if payload is None:
        return ListingStatus.UNKNOWN
    for job in payload.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        if job.get("id") == job_id or job_id in (job.get("jobUrl") or ""):
            html = (job.get("descriptionHtml") or "").strip()
            return classify_http_result(200, html)
    return ListingStatus.CLOSED


async def _probe_generic(client: httpx.AsyncClient, url: str) -> ListingStatus:
    response = await _get(client, url)
    if response is None:
        return ListingStatus.UNKNOWN
    return classify_http_result(response.status_code, response.text)


_ATS_PROBES: tuple[tuple[tuple[str, ...], Callable], ...] = (
    (("greenhouse", "greenhouse_eu"), _probe_greenhouse),
    (("lever", "lever_eu"), _probe_lever),
    (("ashby",), _probe_ashby),
)


async def probe_listing(
    client: httpx.AsyncClient,
    url: str,
    ats_type: str | None = None,
) -> ListingStatus:
    target = (url or "").strip()
    if not target:
        return ListingStatus.UNKNOWN
    key = (ats_type or "").strip().lower()
    for names, probe in _ATS_PROBES:
        if key in names:
            return await probe(client, target)
    if greenhouse_job_ids_from_url(target):
        return await _probe_greenhouse(client, target)
    if _lever_posting_api_url(target):
        return await _probe_lever(client, target)
    if ashby_job_ids_from_url(target):
        return await _probe_ashby(client, target)
    return await _probe_generic(client, target)
