from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from relocation_jobs.fetch.country_runner import run_country_fetch


def _stub_country_catalog(monkeypatch, companies: list[dict]) -> list[int]:
    cancel_calls: list[int] = []
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.list_country_company_stubs",
        lambda country_key: companies,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.get_company",
        lambda country_key, name: {"name": name, "careers_url": f"https://{name}.example/jobs"},
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
    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_repo.request_fetch_run_cancel",
        lambda run_id: cancel_calls.append(run_id),
    )
    return cancel_calls


@pytest.mark.asyncio
async def test_company_timeout_does_not_cancel_remaining_companies(db, monkeypatch):
    del db
    monkeypatch.setenv("FETCH_COMPANY_TIMEOUT_SECONDS", "1")
    companies = [{"name": "FastCo"}, {"name": "SlowCo"}]
    cancel_calls = _stub_country_catalog(monkeypatch, companies)
    logs: list[str] = []

    async def fake_fetch(client, country_key, name, **kwargs):
        if name == "SlowCo":
            await asyncio.sleep(2)
            return f"[1/1] {name} — ok", 0
        return f"[1/1] {name} — ok", 0

    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_and_persist_company",
        AsyncMock(side_effect=fake_fetch),
    )

    new_jobs, done, cancelled = await run_country_fetch(
        MagicMock(),
        "uk",
        run_id=7,
        concurrency=1,
        on_log=logs.append,
    )

    assert cancelled is False
    assert done == 2
    assert cancel_calls == []
    assert any("SlowCo" in line and "timed out" in line for line in logs)
    assert any("FastCo" in line for line in logs)
    assert new_jobs == 0


@pytest.mark.asyncio
async def test_company_timeout_at_concurrency_two_does_not_cancel_country(db, monkeypatch):
    del db
    monkeypatch.setenv("FETCH_COMPANY_TIMEOUT_SECONDS", "1")
    companies = [{"name": "FastCo"}, {"name": "SlowCo"}]
    cancel_calls = _stub_country_catalog(monkeypatch, companies)
    logs: list[str] = []

    async def fake_fetch(client, country_key, name, **kwargs):
        if name == "SlowCo":
            await asyncio.sleep(2)
            return f"[1/1] {name} — ok", 0
        return f"[1/1] {name} — ok", 1

    monkeypatch.setattr(
        "relocation_jobs.fetch.country_runner.fetch_and_persist_company",
        AsyncMock(side_effect=fake_fetch),
    )

    new_jobs, done, cancelled = await run_country_fetch(
        MagicMock(),
        "uk",
        run_id=7,
        concurrency=2,
        on_log=logs.append,
    )

    assert cancelled is False
    assert done == 2
    assert new_jobs == 1
    assert cancel_calls == []
    assert any("SlowCo" in line and "timed out" in line for line in logs)
    assert any("FastCo" in line for line in logs)


def test_country_runner_has_no_thread_pool():
    from relocation_jobs.fetch import country_runner

    source = inspect.getsource(country_runner)
    assert "ThreadPoolExecutor" not in source
    assert "_fetch_one_thread" not in source
    assert "asyncio.run(" not in source
    assert not hasattr(country_runner, "_fetch_one_thread")
