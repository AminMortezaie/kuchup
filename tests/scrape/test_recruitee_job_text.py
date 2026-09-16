from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.http_mock import MockResponse

from relocation_jobs.scrape.job_text import fetch_recruitee_job_detail
from relocation_jobs.scrape.descriptions import needs_recruitee_refetch

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "ats"
    / "recruitee_offer_detail.json"
)
_JOB_URL = "https://acme.recruitee.com/o/backend-developer"


def test_fetch_recruitee_job_detail_combines_description_and_requirements(monkeypatch):
    payload = json.loads(_FIXTURE.read_text())
    list_payload = {
        "offers": [
            {
                "id": 42,
                "slug": "backend-developer",
                "careers_url": _JOB_URL,
            }
        ]
    }

    def fake_get(url, *args, **kwargs):
        if url == "https://acme.recruitee.com/api/offers/":
            return MockResponse(json_data=list_payload)
        if url == "https://acme.recruitee.com/api/offers/42":
            return MockResponse(json_data=payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("relocation_jobs.scrape.job_text.requests.get", fake_get)
    result = fetch_recruitee_job_detail(_JOB_URL)
    assert "Relocation package available including visa sponsorship." in result.text
    assert "What awaits you" in result.text
    assert "TypeScript and React" in result.text
    assert "Ship features end to end" in result.text


def test_needs_recruitee_refetch():
    intro_only = (
        "Are you ready to be a technology leader in the SaaS space? Join epilot!\n\n"
        "We are looking for product minded engineers not only coders."
    )
    full = intro_only + "\n\nWhat awaits you\n\n• Ship features end to end"
    assert needs_recruitee_refetch("") is True
    assert needs_recruitee_refetch(intro_only) is True
    assert needs_recruitee_refetch(full) is False
