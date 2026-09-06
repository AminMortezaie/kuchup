from __future__ import annotations

import re

import requests

from relocation_jobs.core.ats_detection import HEADERS
from relocation_jobs.scrape.listing import listing_job


_SLUG_RE = re.compile(r"https?://([a-z0-9-]+)\.pinpointhq\.com", re.I)
_POSTING_URL_RE = re.compile(
    r"https?://([a-z0-9-]+)\.pinpointhq\.com(?:/[a-z]{2}(?:-[a-z]{2})?)?/postings/"
    r"([0-9a-f-]{36}|\d+)",
    re.I,
)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_JOB_AD_SECTIONS = (
    ("description", ""),
    ("key_responsibilities", "key_responsibilities_header"),
    ("skills_knowledge_expertise", "skills_knowledge_expertise_header"),
    ("benefits", "benefits_header"),
)


def _location_label(posting: dict) -> str:
    loc = posting.get("location") or {}
    if not isinstance(loc, dict):
        return ""
    parts: list[str] = []
    seen: set[str] = set()
    for raw in (loc.get("city"), loc.get("province")):
        text = (raw or "").strip()
        if not text or not any(ch.isalnum() for ch in text):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return ", ".join(parts)


def _strip_html_comments(html: str) -> str:
    return _HTML_COMMENT_RE.sub("", html).strip()


def _posting_matches(posting: dict, posting_id: str) -> bool:
    if str(posting.get("id") or "").strip() == posting_id:
        return True
    haystack = f"{posting.get('url') or ''} {posting.get('path') or ''}".lower()
    return posting_id.lower() in haystack


def pinpointhq_board_slug(ats_url: str) -> str:
    m = _SLUG_RE.search(ats_url or "")
    return m.group(1) if m else ""


def pinpointhq_postings_api_url(slug: str) -> str:
    return f"https://{slug}.pinpointhq.com/postings.json"


def pinpointhq_posting_ids_from_url(url: str) -> tuple[str, str] | None:
    match = _POSTING_URL_RE.search(url or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def pinpointhq_job_ad_html(posting: dict) -> str:
    parts: list[str] = []
    for body_key, header_key in _JOB_AD_SECTIONS:
        text = _strip_html_comments(posting.get(body_key) or "")
        if not text:
            continue
        title = (posting.get(header_key) or "").strip() if header_key else ""
        if title:
            parts.append(f"<h3>{title}</h3>")
        parts.append(text)
    return "\n".join(parts)


def fetch_pinpointhq_job_detail(url: str) -> tuple[str, str]:
    ids = pinpointhq_posting_ids_from_url(url)
    if not ids:
        return "", ""
    slug, posting_id = ids
    try:
        response = requests.get(
            pinpointhq_postings_api_url(slug),
            headers=HEADERS,
            timeout=15,
        )
        if not response.ok:
            return "", ""
        for posting in response.json().get("data") or []:
            if not _posting_matches(posting, posting_id):
                continue
            html = pinpointhq_job_ad_html(posting)
            if not html.strip():
                return "", ""
            return html, _location_label(posting)
    except Exception:
        pass
    return "", ""


async def fetch_pinpointhq_board(
    client,
    board_url: str,
    company: dict,
) -> list[dict]:
    slug = pinpointhq_board_slug(board_url)
    if not slug:
        return []
    response = await client.get(
        pinpointhq_postings_api_url(slug),
        headers=HEADERS,
        timeout=15.0,
    )
    response.raise_for_status()
    jobs: list[dict] = []
    for posting in response.json().get("data") or []:
        title = (posting.get("title") or "").strip()
        url = (posting.get("url") or "").strip()
        if not title or not url:
            continue
        location = _location_label(posting)
        jobs.append(listing_job(title, url, location=location or None))
    return jobs
