from __future__ import annotations

import pytest

from relocation_jobs.core.db import get_connection
from relocation_jobs.notifications import repo as notifications_repo
from relocation_jobs.notifications import service as notifications_service
from relocation_jobs.users.entitlements import set_plan
from relocation_jobs.users.repo import create_user


def test_subscription_upsert_endpoint_unique(db):
    user = create_user("pusha", email="pusha@example.com", google_sub="sub-pusha")
    uid = int(user["id"])
    notifications_repo.upsert_subscription(
        uid,
        endpoint="https://push.example/a",
        p256dh="p256",
        auth="auth",
    )
    notifications_repo.upsert_subscription(
        uid,
        endpoint="https://push.example/a",
        p256dh="p256b",
        auth="authb",
    )
    rows = notifications_repo.list_subscriptions_for_user(uid)
    assert len(rows) == 1
    assert rows[0]["p256dh"] == "p256b"


def test_record_wave_jobs_dedupes_keys(db):
    user = create_user("waveuser", email="waveuser@example.com", google_sub="sub-wave")
    uid = int(user["id"])
    set_plan(uid, "full")
    conn = get_connection()
    row = conn.execute(
        """
        INSERT INTO fetch_runs (
            user_id, country, scope, status, started_at, finished_at, new_jobs
        ) VALUES (%s, 'uk', 'country', 'done', '2026-01-01T00:00:00+00:00',
                  '2026-01-01T01:00:00+00:00', 1)
        RETURNING id
        """,
        (uid,),
    ).fetchone()
    run_id = int(row["id"])
    conn.execute(
        """
        INSERT INTO user_opportunities (
            user_id, country, company_name, newest_fetched, updated_at
        ) VALUES (%s, 'uk', 'Acme Ltd', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """,
        (uid,),
    )
    job = {"url": "https://boards.greenhouse.io/acme/jobs/12345"}
    notifications_service.record_fetch_wave_jobs(run_id, "uk", "Acme Ltd", [job])
    notifications_service.record_fetch_wave_jobs(run_id, "uk", "Acme Ltd", [job])
    assert notifications_repo.count_wave_jobs_for_user(uid, run_id) == 1


def test_save_subscription_rejects_free_plan(db):
    user = create_user("freeonly", email="freeonly@example.com", google_sub="sub-freeonly")
    uid = int(user["id"])
    with pytest.raises(PermissionError):
        notifications_service.save_subscription(
            uid,
            {
                "endpoint": "https://push.example/x",
                "keys": {"p256dh": "p", "auth": "a"},
            },
        )


def test_plan_eligible_for_push():
    assert notifications_service.plan_eligible_for_push("full") is True
    assert notifications_service.plan_eligible_for_push("grandfathered") is True
    assert notifications_service.plan_eligible_for_push("free") is False
