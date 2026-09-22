from __future__ import annotations

import pytest

from relocation_jobs.core.ats_constants import PLAYWRIGHT_REQUIRED_ATS
from relocation_jobs.fetch.worker_kind import worker_includes_ats, worker_kind


def test_http_worker_skips_playwright_required_ats(monkeypatch):
    monkeypatch.setenv("FETCH_WORKER_KIND", "http")
    assert worker_kind() == "http"
    assert worker_includes_ats("greenhouse") is True
    assert worker_includes_ats("ashby") is True
    assert worker_includes_ats("generic") is True
    assert worker_includes_ats("hibob") is False
    assert worker_includes_ats("jibe") is False
    assert worker_includes_ats("atlassian") is False


def test_playwright_worker_only_required_ats(monkeypatch):
    monkeypatch.setenv("FETCH_WORKER_KIND", "playwright")
    monkeypatch.setattr(
        "relocation_jobs.fetch.worker_kind.PLAYWRIGHT_AVAILABLE",
        True,
    )
    assert worker_includes_ats("hibob") is True
    assert worker_includes_ats("jibe") is True
    assert worker_includes_ats("atlassian") is True
    assert worker_includes_ats("greenhouse") is False
    assert worker_includes_ats("generic") is False
    assert worker_includes_ats("ashby") is False


def test_missing_playwright_never_includes_required_ats(monkeypatch):
    monkeypatch.setenv("FETCH_WORKER_KIND", "all")
    monkeypatch.setattr(
        "relocation_jobs.fetch.worker_kind.PLAYWRIGHT_AVAILABLE",
        False,
    )
    for ats in PLAYWRIGHT_REQUIRED_ATS:
        assert worker_includes_ats(ats) is False
    assert worker_includes_ats("greenhouse") is True


def test_unknown_worker_kind_raises(monkeypatch):
    monkeypatch.setenv("FETCH_WORKER_KIND", "go")
    with pytest.raises(ValueError, match="FETCH_WORKER_KIND"):
        worker_kind()


def test_default_kind_follows_playwright_install(monkeypatch):
    monkeypatch.delenv("FETCH_WORKER_KIND", raising=False)
    monkeypatch.setattr(
        "relocation_jobs.fetch.worker_kind.PLAYWRIGHT_AVAILABLE",
        False,
    )
    assert worker_kind() == "http"
    monkeypatch.setattr(
        "relocation_jobs.fetch.worker_kind.PLAYWRIGHT_AVAILABLE",
        True,
    )
    assert worker_kind() == "all"
