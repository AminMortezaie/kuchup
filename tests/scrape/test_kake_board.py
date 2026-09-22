from __future__ import annotations

import pytest

from relocation_jobs.core.ats_detection import _detect_kake_from_url, detect_ats_static
from relocation_jobs.scrape.boards.kake import (
    fetch_kake_board,
    fetch_kake_board_sync,
    kake_board_url,
    parse_kake_board_html,
)

SAMPLE_HTML = """
<div>
  <a href="/jobs/senior-backend-engineer-go-39007733f3d6">Senior Backend Engineer (Go)</a>
  <svg><path d="M0 0"></path></svg>
  <span>Timezone:<!-- --> <strong>GMT-5</strong></span>
  <span>Golang</span>
</div>
<div>
  <a href="/jobs/senior-roku-engineer-b0f632f25d97">Senior Roku Engineer</a>
  <div class="items"></div>
</div>
<div>
  <a href="https://kake.co/jobs/forward-deployed-engineer-5977bc1d7bab">Forward Deployed Engineer</a>
  <span>Timezone: <strong>gmt-3</strong></span>
</div>
<a href="/jobs/senior-backend-engineer-go-39007733f3d6">Senior Backend Engineer (Go)</a>
<a href="/jobs">Jobs</a>
<a href="/about">About</a>
"""


def test_kake_board_url_defaults_to_listing():
    assert kake_board_url("") == "https://kake.co/jobs"
    assert kake_board_url("https://www.kake.co/jobs/some-role-abc") == "https://kake.co/jobs"
    assert kake_board_url("https://example.com/jobs") == "https://kake.co/jobs"


def test_parse_kake_board_html_maps_listing_cards():
    jobs = parse_kake_board_html(SAMPLE_HTML)
    assert len(jobs) == 3
    by_title = {job["title"]: job for job in jobs}
    backend = by_title["Senior Backend Engineer (Go)"]
    assert backend["employer"] == "Kake"
    assert backend["location"] == "Remote, GMT-5"
    assert backend["url"] == "https://kake.co/jobs/senior-backend-engineer-go-39007733f3d6"
    assert by_title["Senior Roku Engineer"]["location"] == "Remote"
    assert by_title["Forward Deployed Engineer"]["location"] == "Remote, GMT-3"
    assert by_title["Forward Deployed Engineer"]["url"] == (
        "https://kake.co/jobs/forward-deployed-engineer-5977bc1d7bab"
    )


def test_detect_kake_from_host_without_fetch():
    assert _detect_kake_from_url("https://kake.co/jobs") == ("kake", "https://kake.co/jobs")
    assert _detect_kake_from_url("https://www.kake.co/jobs/senior-android-engineer-cbd") == (
        "kake",
        "https://kake.co/jobs",
    )
    assert _detect_kake_from_url("https://example.com/jobs") == (None, None)
    assert detect_ats_static("https://kake.co/jobs") == ("kake", "https://kake.co/jobs")


def test_fetch_kake_board_sync_uses_fixture_html(monkeypatch):
    class _Response:
        text = SAMPLE_HTML

        def raise_for_status(self):
            return None

    seen = {}

    def _get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("relocation_jobs.scrape.boards.kake.requests.get", _get)
    jobs = fetch_kake_board_sync("https://kake.co/")
    assert seen["url"] == "https://kake.co/jobs"
    assert len(jobs) == 3
    assert jobs[0]["employer"] == "Kake"


@pytest.mark.asyncio
async def test_fetch_kake_board_and_dispatch(monkeypatch):
    class _Response:
        text = SAMPLE_HTML

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "relocation_jobs.scrape.boards.kake.requests.get",
        lambda *args, **kwargs: _Response(),
    )
    jobs = await fetch_kake_board(None, "https://kake.co/jobs", {"name": "Kake"})
    assert len(jobs) == 3

    from relocation_jobs.scrape.board import fetch_ats_board

    company = {
        "name": "Kake",
        "ats_type": "kake",
        "ats_url": "https://kake.co/jobs",
        "careers_url": "https://kake.co/jobs",
    }
    dispatched = await fetch_ats_board(None, company)
    assert len(dispatched) == 3
    assert dispatched[0]["url"].startswith("https://kake.co/jobs/")
