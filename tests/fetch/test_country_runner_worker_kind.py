from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from relocation_jobs.fetch.country_runner import run_country_fetch


def _stub_country_catalog(monkeypatch, companies: list[dict]) -> None:
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.list_country_company_stubs",
        lambda country_key: companies,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.get_company",
        lambda country_key, name: {"name": name, "ats_type": "greenhouse"},
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.load_country_catalog",
        lambda country_key: {"companies": companies},
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.patch_country_catalog_meta",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_repo.fetch_run_cancel_requested",
        lambda run_id: False,
    )


@pytest.mark.asyncio
async def test_http_worker_skips_playwright_only_companies(db, monkeypatch):
    del db
    monkeypatch.setenv("FETCH_WORKER_KIND", "http")
    companies = [
        {"name": "HttpCo", "ats_type": "greenhouse"},
        {"name": "PwCo", "ats_type": "hibob"},
        {"name": "SourcedCo", "ats_type": "sourced"},
    ]
    _stub_country_catalog(monkeypatch, companies)
    fetched: list[str] = []

    async def fake_fetch(client, country_key, name, **kwargs):
        fetched.append(name)
        return f"[1/1] {name} — ok", 0

    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_and_persist_company",
        AsyncMock(side_effect=fake_fetch),
    )

    new_jobs, done, cancelled = await run_country_fetch(
        MagicMock(),
        "uk",
        run_id=11,
        concurrency=1,
    )

    assert cancelled is False
    assert fetched == ["HttpCo"]
    assert done == 1
    assert new_jobs == 0


@pytest.mark.asyncio
async def test_playwright_worker_only_fetches_required_ats(db, monkeypatch):
    del db
    monkeypatch.setenv("FETCH_WORKER_KIND", "playwright")
    monkeypatch.setattr(
        "relocation_jobs.fetch.worker_kind.PLAYWRIGHT_AVAILABLE",
        True,
    )
    companies = [
        {"name": "HttpCo", "ats_type": "greenhouse"},
        {"name": "PwCo", "ats_type": "jibe"},
        {"name": "GenericCo", "ats_type": "generic"},
    ]
    _stub_country_catalog(monkeypatch, companies)
    fetched: list[str] = []

    async def fake_fetch(client, country_key, name, **kwargs):
        fetched.append(name)
        return f"[1/1] {name} — ok", 0

    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_and_persist_company",
        AsyncMock(side_effect=fake_fetch),
    )

    _new_jobs, done, cancelled = await run_country_fetch(
        MagicMock(),
        "uk",
        run_id=12,
        concurrency=1,
    )

    assert cancelled is False
    assert fetched == ["PwCo"]
    assert done == 1
