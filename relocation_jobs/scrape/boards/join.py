from __future__ import annotations

import json
import re

import requests

from relocation_jobs.core.ats_detection import HEADERS, _detect_join_from_url
from relocation_jobs.scrape.descriptions import html_to_readable
from relocation_jobs.scrape.listing import listing_job

_JOIN_JOB_URL_RE = re.compile(
    r"join\.com/companies/([^/]+)/([^/?#]+)",
    re.I,
)


def parse_join_next_data(html: str) -> tuple[str | None, int | None, list[dict]]:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return None, None, []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None, None, []
    state = data.get("props", {}).get("pageProps", {}).get("initialState", {})
    company = state.get("company") or {}
    jobs_block = state.get("jobs") or {}
    return (
        company.get("domain"),
        company.get("id"),
        list(jobs_block.get("items") or []),
    )


def join_jobs_from_items(items: list[dict], slug: str) -> list[dict]:
    base = f"https://join.com/companies/{slug}"
    jobs: list[dict] = []
    seen: set[str] = set()
    for item in items:
        title = (item.get("title") or "").strip()
        id_param = (item.get("idParam") or "").strip()
        if not title or not id_param:
            continue
        url = f"{base}/{id_param}"
        if url in seen:
            continue
        seen.add(url)
        jobs.append(listing_job(title, url))
    return jobs


def _join_page_job(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    props = data.get("props", {}).get("pageProps", {}) or {}
    for key in ("job", "jobPosting", "posting"):
        job = props.get(key)
        if isinstance(job, dict):
            return job
    state = props.get("initialState") or {}
    job = state.get("job")
    return job if isinstance(job, dict) else {}


def fetch_join_job_detail(url: str) -> tuple[str, str]:
    if not _JOIN_JOB_URL_RE.search(url or ""):
        return "", ""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if not response.ok:
            return "", ""
        job = _join_page_job(response.text)
        html = (job.get("description") or job.get("body") or "").strip()
        if not html:
            return "", ""
        location = (
            (job.get("location") or {}).get("name")
            if isinstance(job.get("location"), dict)
            else (job.get("location") or "")
        )
        return html_to_readable(html), str(location or "").strip()
    except Exception:
        return "", ""


async def fetch_join_board(client, board_url: str, company: dict) -> list[dict]:
    source = board_url or (company.get("careers_url") or "")
    detected = _detect_join_from_url(source)
    if not detected[1]:
        return []
    page_url = detected[1]
    slug_match = re.search(r"join\.com/companies/([a-zA-Z0-9_-]+)", page_url, re.I)
    slug = slug_match.group(1) if slug_match else page_url.rstrip("/").split("/")[-1]
    response = await client.get(page_url, headers=HEADERS, timeout=15.0)
    response.raise_for_status()
    slug_from_page, company_id, items = parse_join_next_data(response.text)
    if slug_from_page:
        slug = slug_from_page
    if company_id:
        try:
            api_response = await client.get(
                f"https://join.com/api/public/companies/{company_id}/jobs",
                headers={**HEADERS, "Accept": "application/json"},
                params={"page": 1, "pageSize": 50},
                timeout=15.0,
            )
            api_response.raise_for_status()
            data = api_response.json()
            api_items = list(data.get("items") or [])
        except Exception:
            api_items = []
        if api_items:
            items = api_items
    return join_jobs_from_items(items, slug)
