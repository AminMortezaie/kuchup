from __future__ import annotations

from urllib.parse import urlparse

from relocation_jobs.core.ats_detection import HEADERS
from relocation_jobs.scrape.listing import listing_job


def recruitee_board_slug(ats_url: str) -> str:
    host = (urlparse(ats_url).hostname or "").lower()
    if not host.endswith(".recruitee.com"):
        return ""
    return host.split(".")[0]


def recruitee_offers_api_url(board_or_slug: str) -> str:
    raw = (board_or_slug or "").strip()
    if not raw:
        return ""
    if "://" not in raw and "." not in raw:
        return f"https://{raw}.recruitee.com/api/offers/"
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if host.endswith(".recruitee.com"):
        slug = host.split(".")[0]
        if not slug or slug in ("www", "api", "careers", "app"):
            return ""
        return f"https://{slug}.recruitee.com/api/offers/"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}/api/offers/"


def recruitee_offer_location(offer: dict) -> str | None:
    location = (offer.get("location") or "").strip()
    if location:
        return location
    parts = [
        (offer.get("city") or "").strip(),
        (offer.get("country") or "").strip(),
    ]
    text = ", ".join(dict.fromkeys(part for part in parts if part))
    return text or None


async def fetch_recruitee_board(client, board_url: str, company: dict) -> list[dict]:
    api_url = recruitee_offers_api_url(board_url)
    if not api_url:
        return []
    response = await client.get(
        api_url,
        headers=HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    jobs: list[dict] = []
    for row in response.json().get("offers") or []:
        title = (row.get("title") or "").strip()
        url = (row.get("careers_url") or board_url).strip()
        if not title or not url:
            continue
        jobs.append(listing_job(title, url, location=recruitee_offer_location(row)))
    return jobs
