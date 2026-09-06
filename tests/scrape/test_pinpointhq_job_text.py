from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.http_mock import MockResponse

from relocation_jobs.scrape.boards.pinpointhq import (
    pinpointhq_job_ad_html,
    pinpointhq_posting_ids_from_url,
)
from relocation_jobs.scrape.descriptions import needs_pinpointhq_refetch
from relocation_jobs.scrape.job_text import fetch_job_detail, fetch_pinpointhq_job_detail

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "ats"
    / "pinpointhq_postings.json"
)
_JOB_URL = "https://acme.pinpointhq.com/en/postings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_API_URL = "https://acme.pinpointhq.com/postings.json"


def test_pinpointhq_posting_ids_from_url():
    assert pinpointhq_posting_ids_from_url(_JOB_URL) == (
        "acme",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert pinpointhq_posting_ids_from_url(
        "https://tabby.pinpointhq.com/postings/62bc787e-a836-459d-ae9f-62d23c1fa949"
    ) == ("tabby", "62bc787e-a836-459d-ae9f-62d23c1fa949")
    assert pinpointhq_posting_ids_from_url("https://acme.pinpointhq.com/postings.json") is None


def test_pinpointhq_job_ad_html_combines_sections():
    payload = json.loads(_FIXTURE.read_text())
    html = pinpointhq_job_ad_html(payload["data"][0])
    assert "Visa sponsorship is available." in html
    assert "<!--block-->" not in html
    assert "<h3>Key Responsibilities</h3>" in html
    assert "Ship backend services in Kotlin" in html
    assert "<h3>Skills, Knowledge & Expertise</h3>" in html
    assert "<h3>Job Benefits</h3>" in html
    assert "Relocation support" in html
    assert "Ignore this posting" not in html


def test_fetch_pinpointhq_job_detail_uses_api(monkeypatch):
    payload = json.loads(_FIXTURE.read_text())

    def fake_get(url, *args, **kwargs):
        assert url == _API_URL
        return MockResponse(json_data=payload)

    monkeypatch.setattr("relocation_jobs.scrape.boards.pinpointhq.requests.get", fake_get)
    result = fetch_pinpointhq_job_detail(_JOB_URL)
    assert "Ship backend services in Kotlin" in result.text
    assert "Visa sponsorship is available." in result.text
    assert "<!--" not in result.text
    assert result.location == "Belgrade"


def test_fetch_job_detail_dispatches_pinpointhq(monkeypatch):
    payload = json.loads(_FIXTURE.read_text())

    def fake_get(url, *args, **kwargs):
        return MockResponse(json_data=payload)

    monkeypatch.setattr("relocation_jobs.scrape.boards.pinpointhq.requests.get", fake_get)
    result = fetch_job_detail(_JOB_URL, "pinpointhq")
    assert "Own the payments platform" in result.text
    assert "Register Your Interest" not in result.text


def test_needs_pinpointhq_refetch():
    chrome = (
        "Senior Backend Engineer - KSA | Tabby Careers\n\nCareers at\n\n"
        "Key Responsibilities\n\nSkills, Knowledge & Expertise\n\n"
        "Not quite right? Register your interest to be notified.\n"
        "View all opportunities at Tabby\nPrivacy Policy\nCookies\nPowered by"
    )
    full = (
        "<p>Build payments APIs.</p>"
        "<h3>Key Responsibilities</h3>"
        "<ul><li>Ship backend services in Kotlin</li></ul>"
    )
    assert needs_pinpointhq_refetch("") is True
    assert needs_pinpointhq_refetch(chrome) is True
    assert needs_pinpointhq_refetch(full) is False
