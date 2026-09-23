from __future__ import annotations

import json
import subprocess

import httpx
import pytest
import respx
from httpx import Response

from relocation_jobs.scrape.board import fetch_ats_board
from relocation_jobs.scrape.boards.greenhouse import greenhouse_jobs_api_url
from relocation_jobs.scrape.go_http import GoScrapeError, go_board_jobs, http_scrape_mode


def _stub(tmp_path, body: str, *, code: int = 0) -> str:
    script = tmp_path / "ats-scrape"
    script.write_text(
        "#!/bin/sh\n"
        "cat >/dev/null\n"
        f"printf '%s\\n' {json.dumps(body)}\n"
        f"exit {code}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return str(script)


@pytest.mark.asyncio
async def test_fetch_ats_board_uses_go_when_binary_present(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(
        tmp_path,
        '[{"title":"Backend Engineer","url":"https://example.com/jobs/1","location":"Berlin"}]',
    ))
    company = {
        "name": "Acme",
        "ats_type": "greenhouse",
        "ats_url": "https://boards.greenhouse.io/acmebackend",
    }
    jobs = await fetch_ats_board(None, company)
    assert jobs == [{
        "title": "Backend Engineer",
        "url": "https://example.com/jobs/1",
        "location": "Berlin",
    }]


@pytest.mark.asyncio
@respx.mock
async def test_python_mode_skips_go_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "python")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "not-json", code=1))
    respx.get(greenhouse_jobs_api_url("acmebackend")).mock(
        return_value=Response(
            200,
            json={
                "jobs": [{
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acmebackend/jobs/9",
                    "location": {"name": "Berlin"},
                }],
            },
        ),
    )
    company = {
        "name": "Acme",
        "ats_type": "greenhouse",
        "ats_url": "https://boards.greenhouse.io/acmebackend",
    }
    async with httpx.AsyncClient() as client:
        jobs = await fetch_ats_board(client, company)
    assert jobs[0]["url"].endswith("/jobs/9")


@pytest.mark.asyncio
@respx.mock
async def test_go_unsupported_falls_back_to_python(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "unsupported", code=2))
    respx.get(greenhouse_jobs_api_url("acmebackend")).mock(
        return_value=Response(
            200,
            json={
                "jobs": [{
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acmebackend/jobs/3",
                    "location": {"name": "Berlin"},
                }],
            },
        ),
    )
    company = {
        "name": "Acme",
        "ats_type": "greenhouse",
        "ats_url": "https://boards.greenhouse.io/acmebackend",
    }
    async with httpx.AsyncClient() as client:
        jobs = await fetch_ats_board(client, company)
    assert jobs[0]["url"].endswith("/jobs/3")


@pytest.mark.asyncio
async def test_go_mode_surfaces_scrape_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "boom", code=1))
    company = {
        "name": "Acme",
        "ats_type": "ashby",
        "ats_url": "https://jobs.ashbyhq.com/acme",
    }
    with pytest.raises(GoScrapeError):
        await fetch_ats_board(None, company)


@pytest.mark.asyncio
async def test_go_mode_keeps_empty_generic_board(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "[]"))
    company = {
        "name": "Acme",
        "ats_type": "generic",
        "careers_url": "https://careers.example.com/",
        "ats_url": "https://careers.example.com/",
    }
    assert await fetch_ats_board(None, company) == []


@pytest.mark.asyncio
@respx.mock
async def test_auto_empty_generic_falls_back_to_python(tmp_path, monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "[]"))
    respx.get("https://careers.example.com/").mock(
        return_value=Response(
            200,
            text='<html><body><a href="/jobs/backend-engineer">Backend Engineer</a></body></html>',
        ),
    )
    company = {
        "name": "Acme",
        "ats_type": "generic",
        "careers_url": "https://careers.example.com/",
        "ats_url": "https://careers.example.com/",
    }
    async with httpx.AsyncClient() as client:
        jobs = await fetch_ats_board(client, company)
    assert jobs[0]["url"].endswith("/jobs/backend-engineer")


def test_missing_binary_in_auto_mode_skips_go(monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.delenv("ATS_SCRAPE_BIN", raising=False)
    assert go_board_jobs({
        "ats_type": "lever",
        "ats_url": "https://jobs.lever.co/acme",
    }) is None


def test_unknown_http_scrape_mode(monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "rust")
    with pytest.raises(ValueError, match="FETCH_HTTP_SCRAPE"):
        http_scrape_mode()


def test_go_mode_requires_a_binary(monkeypatch):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", "/tmp/missing-ats-scrape")
    with pytest.raises(GoScrapeError, match="ATS_SCRAPE_BIN"):
        go_board_jobs({"ats_type": "lever", "ats_url": "https://jobs.lever.co/acme"})


def test_bad_timeout_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ATS_SCRAPE_TIMEOUT_SECONDS", "nope")
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "[]"))
    assert go_board_jobs({"ats_type": "lever", "ats_url": "https://jobs.lever.co/acme"}) == []


def test_auto_invalid_json_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "not-json"))
    assert go_board_jobs({"ats_type": "ashby", "ats_url": "https://jobs.ashbyhq.com/acme"}) is None


def test_go_mode_rejects_non_list_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, '{"jobs":[]}'))
    with pytest.raises(GoScrapeError, match="invalid JSON"):
        go_board_jobs({"ats_type": "ashby", "ats_url": "https://jobs.ashbyhq.com/acme"})


def test_stdout_drops_rows_without_urls(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(
        tmp_path,
        '[{"title":"","url":"https://example.com/j"},{"title":"Backend","url":"https://example.com/j","employer":"Acme"}]',
    ))
    jobs = go_board_jobs({"ats_type": "greenhouse", "ats_url": "https://boards.greenhouse.io/acme"})
    assert jobs == [{
        "title": "Backend",
        "url": "https://example.com/j",
        "employer": "Acme",
    }]


def test_go_mode_rejects_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "not-json"))
    with pytest.raises(GoScrapeError, match="invalid JSON"):
        go_board_jobs({"ats_type": "ashby", "ats_url": "https://jobs.ashbyhq.com/acme"})


def test_go_mode_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "go")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "[]"))

    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr("relocation_jobs.scrape.go_http.subprocess.run", explode)
    with pytest.raises(GoScrapeError, match="timed out"):
        go_board_jobs({"ats_type": "lever", "ats_url": "https://jobs.lever.co/acme"})


def test_auto_timeout_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("FETCH_HTTP_SCRAPE", "auto")
    monkeypatch.setenv("ATS_SCRAPE_BIN", _stub(tmp_path, "[]"))

    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr("relocation_jobs.scrape.go_http.subprocess.run", explode)
    assert go_board_jobs({"ats_type": "lever", "ats_url": "https://jobs.lever.co/acme"}) is None
