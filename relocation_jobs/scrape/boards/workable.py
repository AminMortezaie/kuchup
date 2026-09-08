from __future__ import annotations

import re

import requests

from relocation_jobs.core.ats_detection import HEADERS
from relocation_jobs.scrape.descriptions import html_to_readable
from relocation_jobs.scrape.listing import listing_job

_WORKABLE_POST_BODY = {
    "query": "",
    "location": [],
    "department": [],
    "worktype": [],
    "remote": [],
}


def workable_board_slug(ats_url: str) -> str:
    match = re.search(
        r"apply\.workable\.com/(?:api/v\d+/accounts/)?([a-z0-9-]+)",
        ats_url,
        re.I,
    )
    if match and match.group(1).lower() != "api":
        return match.group(1)
    return ""


def workable_jobs_api_url(slug: str) -> str:
    return f"https://apply.workable.com/api/v2/accounts/{slug}/jobs"


def workable_job_url(slug: str, shortcode: str) -> str:
    return f"https://apply.workable.com/{slug}/j/{shortcode}/"


def workable_job_ids_from_url(url: str) -> tuple[str, str] | None:
    match = re.search(
        r"apply\.workable\.com/([a-z0-9-]+)/j/([A-Za-z0-9]+)",
        url or "",
        re.I,
    )
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_workable_job_detail(url: str) -> tuple[str, str]:
    ids = workable_job_ids_from_url(url)
    if not ids:
        return "", ""
    slug, shortcode = ids
    try:
        response = requests.get(
            f"{workable_jobs_api_url(slug)}/{shortcode}",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=10,
        )
        if not response.ok:
            return "", ""
        data = response.json()
        html = (data.get("description") or data.get("full_description") or "").strip()
        if not html:
            return "", ""
        return html_to_readable(html), workable_location_text(data.get("location"))
    except Exception:
        return "", ""


def workable_location_text(raw: dict | None) -> str:
    if not isinstance(raw, dict):
        return ""
    parts = [
        (raw.get("city") or "").strip(),
        (raw.get("region") or "").strip(),
        (raw.get("country") or "").strip(),
    ]
    return ", ".join(dict.fromkeys(part for part in parts if part))


async def fetch_workable_board(client, board_url: str, company: dict) -> list[dict]:
    slug = workable_board_slug(board_url)
    if not slug:
        return []
    response = await client.post(
        workable_jobs_api_url(slug),
        json=_WORKABLE_POST_BODY,
        headers=HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    jobs: list[dict] = []
    for row in response.json().get("results") or []:
        title = (row.get("title") or "").strip()
        shortcode = (row.get("shortcode") or "").strip()
        if not title or not shortcode:
            continue
        jobs.append(
            listing_job(
                title,
                workable_job_url(slug, shortcode),
                location=workable_location_text(row.get("location")),
            )
        )
    return jobs
