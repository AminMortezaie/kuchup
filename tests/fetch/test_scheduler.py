from __future__ import annotations

import pytest

from relocation_jobs.fetch.scheduler import (
    run_fetch_cycle,
    schedule_concurrency,
    schedule_countries,
    schedule_enabled,
)


def test_schedule_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("FETCH_SCHEDULE_ENABLED", raising=False)
    assert schedule_enabled() is False
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    assert schedule_enabled() is True


def test_schedule_countries_defaults_to_supported(monkeypatch):
    monkeypatch.delenv("FETCH_SCHEDULE_COUNTRIES", raising=False)
    countries = schedule_countries()
    assert "uk" in countries
    assert "netherlands" in countries


def test_schedule_countries_override(monkeypatch):
    monkeypatch.setenv("FETCH_SCHEDULE_COUNTRIES", "uk,netherlands")
    assert schedule_countries() == ("uk", "netherlands")


def test_schedule_concurrency_defaults_to_two(monkeypatch):
    monkeypatch.delenv("FETCH_SCHEDULE_CONCURRENCY", raising=False)
    assert schedule_concurrency() == 2


def test_schedule_concurrency_caps_at_max(monkeypatch):
    monkeypatch.setenv("FETCH_SCHEDULE_CONCURRENCY", "99")
    from relocation_jobs.core.ats_constants import MAX_CONCURRENCY

    assert schedule_concurrency() == MAX_CONCURRENCY


def test_run_fetch_cycle_skips_when_busy(db, monkeypatch):
    from relocation_jobs.users.repo import resolve_scheduler_user_id

    del db
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    monkeypatch.setattr(
        "relocation_jobs.fetch.state.fetch_is_running",
        lambda: True,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.scheduler.run_listing_check_cycle",
        lambda: {"skipped": True, "reason": "busy"},
    )
    user_id = resolve_scheduler_user_id()

    result = run_fetch_cycle(user_id=user_id)

    assert result["skipped"] is True
    assert result["reason"] == "fetch_busy"


def test_run_fetch_cycle_starts_configured_countries(db, monkeypatch):
    from relocation_jobs.users.repo import resolve_scheduler_user_id

    del db
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    monkeypatch.setenv("FETCH_SCHEDULE_COUNTRIES", "uk,netherlands")
    monkeypatch.setenv("FETCH_SCHEDULE_CONCURRENCY", "2")

    started: list[tuple[int, str, int]] = []

    def fake_run_country_fetch_blocking(**kwargs):
        started.append((kwargs["user_id"], kwargs["country_key"], kwargs["concurrency"]))
        return len(started)

    monkeypatch.setattr(
        "relocation_jobs.fetch.scheduler.run_country_fetch_blocking",
        fake_run_country_fetch_blocking,
    )

    user_id = resolve_scheduler_user_id()
    result = run_fetch_cycle(user_id=user_id)

    assert result["skipped"] is False
    assert result["started"] == ["uk", "netherlands"]
    assert started == [
        (user_id, "uk", 2),
        (user_id, "netherlands", 2),
    ]


def test_run_fetch_cycle_abandons_on_country_timeout(db, monkeypatch):
    from relocation_jobs.users.repo import resolve_scheduler_user_id

    del db
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    monkeypatch.setenv("FETCH_SCHEDULE_COUNTRIES", "uk")

    abandoned: list[dict] = []

    def fake_abandon(*, result_line: str) -> None:
        abandoned.append({"result_line": result_line})

    def fake_run_country_fetch_blocking(**kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(
        "relocation_jobs.fetch.scheduler.run_country_fetch_blocking",
        fake_run_country_fetch_blocking,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.state.abandon_fetch_after_timeout",
        fake_abandon,
    )

    user_id = resolve_scheduler_user_id()
    result = run_fetch_cycle(user_id=user_id)

    assert result["skipped"] is False
    assert result["started"] == []
    assert result["not_started"] == ["uk"]
    assert len(abandoned) == 1
    assert "timed out" in abandoned[0]["result_line"]


def test_run_scheduled_pass_runs_listing_check_first(db, monkeypatch):
    from relocation_jobs.users.repo import resolve_scheduler_user_id
    from relocation_jobs.fetch.scheduler import run_scheduled_pass

    del db
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    monkeypatch.setenv("FETCH_SCHEDULE_COUNTRIES", "uk")
    order: list[str] = []

    def fake_listing_check():
        order.append("listing")
        return {"skipped": False, "probed": 3, "closed": 1, "unknown": 0}

    def fake_run_country_fetch_blocking(**kwargs):
        order.append("country")
        return 1

    monkeypatch.setattr(
        "relocation_jobs.fetch.scheduler.run_listing_check_cycle",
        fake_listing_check,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.scheduler.run_country_fetch_blocking",
        fake_run_country_fetch_blocking,
    )

    result = run_scheduled_pass(user_id=resolve_scheduler_user_id())

    assert order == ["listing", "country"]
    assert result["listing_check"]["closed"] == 1


def test_run_fetch_cycle_disabled(monkeypatch):
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "0")
    result = run_fetch_cycle(user_id=1)
    assert result["skipped"] is True
    assert result["reason"] == "schedule_disabled"


def test_resolve_scheduler_user_id(db):
    from relocation_jobs.users.repo import resolve_scheduler_user_id

    del db
    user_id = resolve_scheduler_user_id()
    assert user_id > 0


def test_resolve_scheduler_user_id_missing_user(monkeypatch):
    from relocation_jobs.users.repo import resolve_scheduler_user_id

    class _FakeConn:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

    class _FakeRead:
        def __enter__(self):
            return _FakeConn()

        def __exit__(self, *_args):
            return False

    monkeypatch.setenv("PANEL_ADMIN_USER", "no-such-admin")
    monkeypatch.setattr("relocation_jobs.users.repo.db_read", lambda: _FakeRead())
    monkeypatch.setattr("relocation_jobs.users.repo.get_user_by_username", lambda _name: None)
    with pytest.raises(LookupError, match="PANEL_ADMIN_EMAILS|Scheduler admin"):
        resolve_scheduler_user_id()
