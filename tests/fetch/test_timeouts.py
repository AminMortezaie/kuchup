from __future__ import annotations

from relocation_jobs.fetch.timeouts import (
    company_timeout_seconds,
    country_timeout_seconds,
    fetch_job_max_attempts,
    fetch_job_retry_seconds,
    fetch_job_stale_seconds,
    playwright_board_timeout_seconds,
)


def test_company_timeout_defaults(monkeypatch):
    monkeypatch.delenv("FETCH_COMPANY_TIMEOUT_SECONDS", raising=False)
    assert company_timeout_seconds() == 300


def test_company_timeout_override(monkeypatch):
    monkeypatch.setenv("FETCH_COMPANY_TIMEOUT_SECONDS", "120")
    assert company_timeout_seconds() == 120


def test_company_timeout_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("FETCH_COMPANY_TIMEOUT_SECONDS", "nope")
    assert company_timeout_seconds() == 300


def test_company_timeout_minimum_one(monkeypatch):
    monkeypatch.setenv("FETCH_COMPANY_TIMEOUT_SECONDS", "0")
    assert company_timeout_seconds() == 1


def test_country_timeout_defaults(monkeypatch):
    monkeypatch.delenv("FETCH_COUNTRY_TIMEOUT_SECONDS", raising=False)
    assert country_timeout_seconds() == 2700


def test_playwright_timeout_defaults(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_BOARD_TIMEOUT_SECONDS", raising=False)
    assert playwright_board_timeout_seconds() == 90


def test_playwright_timeout_override(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_BOARD_TIMEOUT_SECONDS", "30")
    assert playwright_board_timeout_seconds() == 30


def test_fetch_job_retry_defaults(monkeypatch):
    monkeypatch.delenv("FETCH_JOB_RETRY_SECONDS", raising=False)
    monkeypatch.delenv("FETCH_JOB_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("FETCH_JOB_STALE_SECONDS", raising=False)
    monkeypatch.delenv("FETCH_COMPANY_TIMEOUT_SECONDS", raising=False)
    assert fetch_job_retry_seconds() == 60
    assert fetch_job_max_attempts() == 3
    assert fetch_job_stale_seconds() == 360


def test_fetch_job_retry_allows_zero(monkeypatch):
    monkeypatch.setenv("FETCH_JOB_RETRY_SECONDS", "0")
    assert fetch_job_retry_seconds() == 0
