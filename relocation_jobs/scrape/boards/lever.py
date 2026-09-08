from __future__ import annotations

import re

from relocation_jobs.core.ats_detection import HEADERS
from relocation_jobs.scrape.listing import listing_job

_LEVER_POSTING_RE = re.compile(r"lever\.co/([^/]+)/([0-9a-f-]{36})", re.I)


def lever_board_slug(ats_url: str) -> str:
    return ats_url.rstrip("/").split("/")[-1].split("?")[0]


def lever_api_host(ats_url: str) -> str:
    return "jobs.eu.lever.co" if "eu.lever" in ats_url else "api.lever.co"


def lever_postings_api_url(slug: str, *, ats_url: str) -> str:
    host = lever_api_host(ats_url)
    return f"https://{host}/v0/postings/{slug}?mode=json"


def lever_posting_ids_from_url(url: str) -> tuple[str, str] | None:
    match = _LEVER_POSTING_RE.search(url or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def lever_posting_api_url(url: str) -> str | None:
    ids = lever_posting_ids_from_url(url)
    if not ids:
        return None
    slug, posting_id = ids
    return f"https://{lever_api_host(url)}/v0/postings/{slug}/{posting_id}"


async def fetch_lever_board(client, board_url: str, company: dict) -> list[dict]:
    slug = lever_board_slug(board_url)
    if not slug:
        return []
    response = await client.get(
        lever_postings_api_url(slug, ats_url=board_url),
        headers=HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    jobs: list[dict] = []
    for row in response.json():
        title = (row.get("text") or "").strip()
        url = (row.get("hostedUrl") or board_url).strip()
        if not title or not url:
            continue
        location = (row.get("categories") or {}).get("location")
        plain = (row.get("descriptionPlain") or "").strip()
        jobs.append(
            listing_job(title, url, location=location, description_text=plain or None)
        )
    return jobs
