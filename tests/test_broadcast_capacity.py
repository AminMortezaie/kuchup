from __future__ import annotations

from relocation_jobs.broadcast.apply import apply_capacity_to_companies
from relocation_jobs.broadcast import repo
from relocation_jobs.broadcast import service as broadcast_service
from relocation_jobs.broadcast.types import CapacityLimits, PositionAssignment, RevealEvent
from relocation_jobs.credits.service import credit_balance
from relocation_jobs.credits import repo as credits_repo
from relocation_jobs.users.repo import create_user


def _job(index: int) -> dict:
    return {
        "idempotency_key": f"job-{index}",
        "url": f"https://example.com/jobs/{index}",
        "title": f"Engineer {index}",
    }


def test_initial_assignments_do_not_consume_monthly_budget(db):
    user = create_user("broadcast-free", email="broadcast@example.com", google_sub="sub-broadcast")
    uid = int(user["id"])
    assignments = repo.ensure_company_assignments(
        uid,
        "germany",
        "Acme",
        [_job(i) for i in range(1, 6)],
        active_target=3,
        period_key="2026-08",
    )
    assert len(assignments) == 3
    assert repo.consumed_count(uid, period_key="2026-08") == 0


def test_explicit_action_is_deduplicated_without_free_board_refill(db):
    user = create_user("broadcast-action", email="action@example.com", google_sub="sub-action")
    uid = int(user["id"])
    jobs = [_job(i) for i in range(1, 6)]
    repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key="2026-08",
    )
    first = repo.mark_assignment_consumed(
        uid,
        country="germany",
        company_name="Acme",
        job_key="job-1",
        job_url=jobs[0]["url"],
        job_title=jobs[0]["title"],
        action_kind="seen",
        period_key="2026-08",
    )
    duplicate = repo.mark_assignment_consumed(
        uid,
        country="germany",
        company_name="Acme",
        job_key="job-1",
        job_url=jobs[0]["url"],
        job_title=jobs[0]["title"],
        action_kind="applied",
        period_key="2026-08",
    )
    assignments = repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key="2026-08",
    )
    assert first is True
    assert duplicate is False
    assert len(assignments) == 3
    assert sum(item.consumed_at is None for item in assignments) == 2


def test_position_budget_resets_by_month(db):
    user = create_user("broadcast-reset", email="reset@example.com", google_sub="sub-reset")
    uid = int(user["id"])
    job = _job(1)
    august = repo.mark_assignment_consumed(
        uid,
        country="germany",
        company_name="Acme",
        job_key=job["idempotency_key"],
        job_url=job["url"],
        job_title=job["title"],
        action_kind="seen",
        period_key="2026-08",
    )
    september = repo.mark_assignment_consumed(
        uid,
        country="germany",
        company_name="Acme",
        job_key=job["idempotency_key"],
        job_url=job["url"],
        job_title=job["title"],
        action_kind="seen",
        period_key="2026-09",
    )
    assert august is True
    assert september is True
    assert repo.consumed_count(uid, period_key="2026-08") == 1
    assert repo.consumed_count(uid, period_key="2026-09") == 1


def test_assigned_role_remains_visible_after_catalog_removal():
    assignment = PositionAssignment(
        period_key="2026-08",
        country="germany",
        company_name="Acme",
        job_key="gone-job",
        job_url="https://example.com/jobs/gone",
        job_title="Saved Engineer",
        assigned_at="2026-08-01T00:00:00Z",
    )
    companies = [{"country": "germany", "name": "Acme", "jobs": []}]
    result = apply_capacity_to_companies(
        companies,
        limits=CapacityLimits(10, 3, 30),
        assignments=[assignment],
    )
    assert result[0]["jobs"][0]["title"] == "Saved Engineer"
    assert result[0]["jobs"][0]["listing_unavailable"] is True


def test_filtered_assigned_role_is_not_mislabeled_as_removed():
    assignment = PositionAssignment(
        period_key="2026-08",
        country="germany",
        company_name="Acme",
        job_key="filtered-job",
        job_url="https://example.com/jobs/filtered",
        job_title="Filtered Engineer",
        assigned_at="2026-08-01T00:00:00Z",
    )
    result = apply_capacity_to_companies(
        [{"country": "germany", "name": "Acme", "jobs": []}],
        limits=CapacityLimits(10, 3, 30),
        assignments=[assignment],
        current_assignment_keys={("germany", "acme", "filtered-job")},
    )
    assert result[0]["jobs"] == []


def test_action_spends_credit_only_when_replacement_is_assigned(db, monkeypatch):
    user = create_user(
        "broadcast-wallet",
        email="wallet@example.com",
        google_sub="sub-wallet",
    )
    uid = int(user["id"])
    jobs = [_job(i) for i in range(1, 5)]
    period = repo.current_period_key()
    repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key=period,
    )
    monkeypatch.setattr(broadcast_service, "_raw_jobs", lambda country, company: jobs)
    event = RevealEvent(
        country="germany",
        company_name="Acme",
        kind="seen",
        job_url=jobs[0]["url"],
        job_key=jobs[0]["idempotency_key"],
        job_title=jobs[0]["title"],
    )
    first = broadcast_service.record_touch_and_maybe_reveal(uid, event)
    duplicate = broadcast_service.record_touch_and_maybe_reveal(uid, event)
    assert first["expanded"] is True
    assert first["credits_spent"] == 1
    assert duplicate["reason"] == "already_counted"
    assert credit_balance(uid).total == 29


def test_action_with_no_replacement_spends_no_credit(db, monkeypatch):
    user = create_user(
        "broadcast-no-replacement",
        email="no-replacement@example.com",
        google_sub="sub-no-replacement",
    )
    uid = int(user["id"])
    jobs = [_job(i) for i in range(1, 4)]
    period = repo.current_period_key()
    repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key=period,
    )
    monkeypatch.setattr(broadcast_service, "_raw_jobs", lambda country, company: jobs)
    result = broadcast_service.record_touch_and_maybe_reveal(
        uid,
        RevealEvent(
            country="germany",
            company_name="Acme",
            kind="seen",
            job_url=jobs[0]["url"],
            job_key=jobs[0]["idempotency_key"],
            job_title=jobs[0]["title"],
        ),
    )
    assert result["reason"] == "no_replacement"
    assert credit_balance(uid).total == 30


def test_empty_wallet_does_not_refill_on_board_read(db, monkeypatch):
    user = create_user(
        "broadcast-empty-wallet",
        email="empty-wallet@example.com",
        google_sub="sub-empty-wallet",
    )
    uid = int(user["id"])
    jobs = [_job(i) for i in range(1, 5)]
    period = repo.current_period_key()
    repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key=period,
    )
    broadcast_service.capacity_meta_for_user(uid)
    for index in range(30):
        credits_repo.spend_credits(
            uid,
            cost=1,
            operation="test",
            idempotency_key=f"drain:{index}",
        )
    monkeypatch.setattr(broadcast_service, "_raw_jobs", lambda country, company: jobs)
    result = broadcast_service.record_touch_and_maybe_reveal(
        uid,
        RevealEvent(
            country="germany",
            company_name="Acme",
            kind="seen",
            job_url=jobs[0]["url"],
            job_key=jobs[0]["idempotency_key"],
            job_title=jobs[0]["title"],
        ),
    )
    assignments = repo.ensure_company_assignments(
        uid, "germany", "Acme", jobs, active_target=3, period_key=period,
    )
    assert result["reason"] == "credits_exhausted"
    assert len(assignments) == 3
    assert sum(item.consumed_at is None for item in assignments) == 2
