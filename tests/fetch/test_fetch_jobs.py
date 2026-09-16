from __future__ import annotations

import inspect

import pytest

from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch.queue import drain_company_fetch_jobs, enqueue_country_company_jobs
from relocation_jobs.fetch.types import FetchJobStatus


def test_claim_sql_uses_skip_locked():
    source = inspect.getsource(fetch_repo.claim_fetch_jobs)
    assert "FOR UPDATE SKIP LOCKED" in source


def test_enqueue_company_job_is_idempotent_while_active(db):
    first = fetch_repo.enqueue_company_fetch_job(
        country="uk",
        company_name="Acme Backend Ltd",
        payload={"ats_type": "greenhouse"},
    )
    second = fetch_repo.enqueue_company_fetch_job(
        country="uk",
        company_name="Acme Backend Ltd",
    )
    assert first == second
    rows = fetch_repo.list_fetch_jobs(country="uk", status=FetchJobStatus.QUEUED)
    assert len(rows) == 1
    assert rows[0].company_name == "Acme Backend Ltd"


def test_claim_returns_distinct_jobs(db):
    first = fetch_repo.enqueue_company_fetch_job(country="uk", company_name="Acme")
    second = fetch_repo.enqueue_company_fetch_job(country="uk", company_name="Beta")
    claimed_one = fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1)
    claimed_two = fetch_repo.claim_fetch_jobs(worker_id="w2", limit=1)
    assert [job.id for job in claimed_one] == [first]
    assert [job.id for job in claimed_two] == [second]
    assert claimed_one[0].status == FetchJobStatus.CLAIMED
    assert claimed_one[0].claimed_by == "w1"


def test_fail_retries_then_marks_dead(db, monkeypatch):
    monkeypatch.setenv("FETCH_JOB_RETRY_SECONDS", "0")
    job_id = fetch_repo.enqueue_company_fetch_job(
        country="uk",
        company_name="Flaky Co",
        max_attempts=2,
    )
    claimed = fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1)
    assert claimed[0].id == job_id
    retried = fetch_repo.fail_fetch_job(job_id, error_message="timeout", retry_seconds=0)
    assert retried is not None
    assert retried.status == FetchJobStatus.QUEUED
    assert retried.attempts == 1

    claimed_again = fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1)
    assert claimed_again[0].id == job_id
    dead = fetch_repo.fail_fetch_job(job_id, error_message="timeout again", retry_seconds=0)
    assert dead is not None
    assert dead.status == FetchJobStatus.DEAD
    assert dead.attempts == 2
    assert fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1) == []


def test_complete_fetch_job_marks_done(db):
    job_id = fetch_repo.enqueue_company_fetch_job(country="uk", company_name="Acme")
    fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1)
    done = fetch_repo.complete_fetch_job(job_id)
    assert done is not None
    assert done.status == FetchJobStatus.DONE
    assert done.finished_at
    assert fetch_repo.count_open_fetch_jobs(country="uk") == 0


def test_reclaim_stale_claimed_jobs(db):
    job_id = fetch_repo.enqueue_company_fetch_job(country="uk", company_name="Stuck Co")
    fetch_repo.claim_fetch_jobs(worker_id="w1", limit=1)
    reclaimed = fetch_repo.reclaim_stale_claimed_fetch_jobs(
        stale_seconds=1,
        now="2099-01-01T00:00:01+00:00",
    )
    assert reclaimed == 1
    job = fetch_repo.get_fetch_job(job_id)
    assert job is not None
    assert job.status == FetchJobStatus.QUEUED
    assert job.claimed_by is None


def test_enqueue_country_company_jobs_from_catalog(seeded_catalog_v2):
    count = enqueue_country_company_jobs("uk", fetch_run_id=9, user_id=1)
    assert count == 1
    rows = fetch_repo.list_fetch_jobs(country="uk")
    assert len(rows) == 1
    assert rows[0].company_name == "Acme Backend Ltd"
    assert rows[0].fetch_run_id == 9
    assert rows[0].payload.get("ats_type") == "greenhouse"


@pytest.mark.asyncio
async def test_drain_marks_job_done(seeded_catalog_v2, monkeypatch):
    enqueue_country_company_jobs("uk", fetch_run_id=4)

    async def fake_persist(client, country_key, name, **kwargs):
        return f"[1/1] {name} — 1 matching job(s)", 1

    monkeypatch.setattr(
        "relocation_jobs.fetch.queue.fetch_and_persist_company",
        fake_persist,
    )

    new_jobs, done, cancelled, countries = await drain_company_fetch_jobs(
        None,
        concurrency=1,
        country="uk",
    )
    assert cancelled is False
    assert done == 1
    assert new_jobs == 1
    assert countries == {"uk"}
    assert fetch_repo.list_fetch_jobs(country="uk")[0].status == FetchJobStatus.DONE


@pytest.mark.asyncio
async def test_drain_writes_catalog_and_attempt(seeded_catalog_v2, monkeypatch):
    from relocation_jobs.catalog.repo import get_company
    from relocation_jobs.fetch.pipeline import fetch_and_persist_company
    from relocation_jobs.fetch.types import AttemptStatus

    enqueue_country_company_jobs("uk")

    async def fake_board(_client, company, **kwargs):
        return [
            {
                "title": "Backend Engineer",
                "url": "https://boards.greenhouse.io/acmebackend/jobs/555555?gh_jid=555555",
            },
        ]

    async def persist_with_board(client, country_key, name, **kwargs):
        kwargs.pop("fetch_board", None)
        return await fetch_and_persist_company(
            client,
            country_key,
            name,
            fetch_board=fake_board,
            **kwargs,
        )

    monkeypatch.setattr(
        "relocation_jobs.fetch.queue.fetch_and_persist_company",
        persist_with_board,
    )

    new_jobs, done, cancelled, _countries = await drain_company_fetch_jobs(
        None,
        concurrency=1,
        country="uk",
    )
    assert cancelled is False
    assert done == 1
    assert new_jobs == 1
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    urls = {job["url"] for job in company["matching_jobs"]}
    assert "https://boards.greenhouse.io/acmebackend/jobs/555555?gh_jid=555555" in urls
    attempts = fetch_repo.list_attempts(country="uk", company_name="Acme Backend Ltd")
    assert len(attempts) == 1
    assert attempts[0].status == AttemptStatus.OK
    assert fetch_repo.list_fetch_jobs(country="uk")[0].status == FetchJobStatus.DONE


@pytest.mark.asyncio
async def test_drain_retries_failed_job_then_completes(seeded_catalog_v2, monkeypatch):
    monkeypatch.setenv("FETCH_JOB_RETRY_SECONDS", "0")
    monkeypatch.setenv("FETCH_JOB_MAX_ATTEMPTS", "3")
    enqueue_country_company_jobs("uk")
    calls: list[str] = []

    async def flaky_persist(client, country_key, name, **kwargs):
        calls.append(name)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return f"[1/1] {name} — ok", 0

    monkeypatch.setattr(
        "relocation_jobs.fetch.queue.fetch_and_persist_company",
        flaky_persist,
    )

    new_jobs, done, cancelled, _countries = await drain_company_fetch_jobs(
        None,
        concurrency=1,
        country="uk",
    )
    assert cancelled is False
    assert done == 1
    assert new_jobs == 0
    assert len(calls) == 2
    assert fetch_repo.list_fetch_jobs(country="uk")[0].status == FetchJobStatus.DONE
