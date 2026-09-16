from __future__ import annotations

from unittest.mock import AsyncMock

from relocation_jobs.fetch.runner import run_country_fetch_blocking
from relocation_jobs.users.repo import get_user_by_username


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def test_blocking_country_fetch_enqueues_and_drains_queue(db, monkeypatch):
    del db
    calls: list[tuple] = []

    def fake_enqueue(country_key, **kwargs):
        calls.append(("enqueue", country_key, kwargs.get("fetch_run_id")))
        return 1

    async def fake_drain(client, **kwargs):
        calls.append(("drain", kwargs.get("country"), kwargs.get("fetch_run_id")))
        return 2, 1, False, {kwargs.get("country")}

    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.enqueue_country_company_jobs",
        fake_enqueue,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.drain_company_fetch_jobs",
        fake_drain,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.make_fetch_client",
        lambda **kwargs: _FakeClient(),
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.enqueue_country_opportunity_refresh",
        lambda country: calls.append(("refresh", country)),
    )

    user_id = get_user_by_username("admin")["id"]
    run_id = run_country_fetch_blocking(
        user_id=user_id,
        country_key="uk",
        concurrency=1,
        timeout=5,
    )
    assert run_id > 0
    assert calls[0][0] == "enqueue"
    assert calls[1][0] == "drain"
    assert calls[1][1] == "uk"
    assert calls[1][2] == run_id
    assert ("refresh", "uk") in calls


def test_recover_pending_jobs_drains_leftovers(db, monkeypatch):
    from relocation_jobs.fetch.runner import recover_pending_fetch_jobs_blocking

    del db
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.fetch_repo.count_open_fetch_jobs",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.fetch_repo.reclaim_stale_claimed_fetch_jobs",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.drain_company_fetch_jobs",
        AsyncMock(return_value=(1, 1, False, {"uk"})),
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.make_fetch_client",
        lambda **kwargs: _FakeClient(),
    )
    refreshed: list[str] = []
    monkeypatch.setattr(
        "relocation_jobs.fetch.runner.enqueue_country_opportunity_refresh",
        lambda country: refreshed.append(country),
    )

    result = recover_pending_fetch_jobs_blocking(concurrency=2)
    assert result["done"] == 1
    assert result["countries"] == ["uk"]
    assert refreshed == ["uk"]
