from __future__ import annotations

from pathlib import Path

from tests.helpers.http_mock import MockResponse

from relocation_jobs.scrape.boards.personio import fetch_personio_board_sync

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ats" / "personio.xml"


def test_personio_xml_board_keeps_job_descriptions(monkeypatch):
    xml = _FIXTURE.read_text(encoding="utf-8")

    def fake_get(url, *args, **kwargs):
        assert url.endswith("/xml")
        return MockResponse(text=xml)

    monkeypatch.setattr("relocation_jobs.scrape.boards.personio.requests.get", fake_get)
    jobs = fetch_personio_board_sync("https://acme.jobs.personio.de/")
    platform = next(job for job in jobs if job["title"] == "Platform Engineer")
    assert "Build APIs" in platform["description_text"]
    assert "Your mission" in platform["description_text"]
    recruiter = next(job for job in jobs if job["title"] == "Recruiter")
    assert "description_text" not in recruiter
