from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import requests

from relocation_jobs.core.ats_detection import HEADERS
from relocation_jobs.scrape.boards._async import run_sync
from relocation_jobs.scrape.listing import listing_job

DEFAULT_KAKE_BOARD = "https://kake.co/jobs"
DEFAULT_EMPLOYER = "Kake"

_JOB_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bhref="(?P<href>(?:https?://(?:www\.)?kake\.co)?/jobs/(?P<slug>[a-z0-9][a-z0-9-]{3,}))"[^>]*>'
    r"(?P<title>[^<]+)</a>",
    re.I,
)
_TZ_RE = re.compile(r"Timezone:\s*(GMT[+-]\d+)", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.I | re.S)
_CARD_WINDOW = 8000


def kake_board_url(board_url: str) -> str:
    raw = (board_url or "").strip()
    if not raw:
        return DEFAULT_KAKE_BOARD
    host = (urlparse(raw).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "kake.co":
        return DEFAULT_KAKE_BOARD
    return DEFAULT_KAKE_BOARD


def _plain_text(raw: str) -> str:
    text = _SVG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _absolute_job_url(href: str) -> str:
    path = urlparse(href).path if "://" in href else href.split("?", 1)[0]
    slug = path.strip("/").split("/")[-1]
    return f"https://kake.co/jobs/{slug}"


def _location_from_card(card_html: str) -> str:
    match = _TZ_RE.search(_plain_text(card_html))
    if not match:
        return "Remote"
    return f"Remote, {match.group(1).upper()}"


def _job_from_anchor(page_html: str, matches: list, index: int, seen: set[str]) -> dict | None:
    match = matches[index]
    title = re.sub(r"\s+", " ", html.unescape(match.group("title") or "")).strip()
    url = _absolute_job_url(match.group("href") or "")
    if not title or url in seen:
        return None
    seen.add(url)
    next_start = matches[index + 1].start() if index + 1 < len(matches) else len(page_html)
    end = min(next_start, match.end() + _CARD_WINDOW)
    return listing_job(
        title,
        url,
        location=_location_from_card(page_html[match.end():end]),
        employer=DEFAULT_EMPLOYER,
    )


def parse_kake_board_html(page_html: str) -> list[dict]:
    text = page_html or ""
    matches = list(_JOB_ANCHOR_RE.finditer(text))
    seen: set[str] = set()
    jobs: list[dict] = []
    for index in range(len(matches)):
        job = _job_from_anchor(text, matches, index, seen)
        if job is not None:
            jobs.append(job)
    return jobs


def fetch_kake_board_sync(board_url: str) -> list[dict]:
    url = kake_board_url(board_url)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return parse_kake_board_html(response.text)


async def fetch_kake_board(client, board_url: str, company: dict) -> list[dict]:
    url = board_url or (company.get("ats_url") or company.get("careers_url") or "")
    return await run_sync(fetch_kake_board_sync, url)
