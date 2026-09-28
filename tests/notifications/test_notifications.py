from __future__ import annotations

import pytest

from relocation_jobs.core.db import get_connection
from relocation_jobs.notifications import copy as notification_copy
from relocation_jobs.notifications import repo as notifications_repo
from relocation_jobs.notifications import send as push_send
from relocation_jobs.notifications import service as notifications_service
from relocation_jobs.users.entitlements import set_plan
from relocation_jobs.users.repo import create_user


def test_new_jobs_notification_body_plural_and_singular():
    assert notification_copy.new_jobs_notification_body(1) == "1 new job found!"
    assert notification_copy.new_jobs_notification_body(7) == "7 new jobs found!"


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


def test_send_after_country_wave_full_only_and_positive_count(db, monkeypatch):
    full_user = create_user("fullpush", email="fullpush@example.com", google_sub="sub-fullpush")
    free_user = create_user("freepush", email="freepush@example.com", google_sub="sub-freepush")
    full_id = int(full_user["id"])
    free_id = int(free_user["id"])
    set_plan(full_id, "full")

    notifications_repo.upsert_subscription(
        full_id,
        endpoint="https://push.example/full",
        p256dh="p256",
        auth="auth",
    )
    notifications_repo.upsert_subscription(
        free_id,
        endpoint="https://push.example/free",
        p256dh="p256",
        auth="auth",
    )

    conn = get_connection()
    row = conn.execute(
        """
        INSERT INTO fetch_runs (
            user_id, country, scope, status, started_at, finished_at, new_jobs
        ) VALUES (%s, %s, 'country', 'done', '2026-01-01T00:00:00+00:00',
                  '2026-01-01T01:00:00+00:00', 2)
        RETURNING id
        """,
        (full_id, "uk"),
    ).fetchone()
    run_id = int(row["id"])
    conn.execute(
        """
        INSERT INTO user_opportunities (
            user_id, country, company_name, newest_fetched, updated_at
        ) VALUES (%s, 'uk', 'Acme Ltd', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """,
        (full_id,),
    )
    conn.execute(
        """
        INSERT INTO user_opportunities (
            user_id, country, company_name, newest_fetched, updated_at
        ) VALUES (%s, 'uk', 'Other Co', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """,
        (free_id,),
    )

    notifications_repo.record_wave_jobs(run_id, "uk", "Acme Ltd", ["job-key-1", "job-key-2"])
    notifications_repo.record_wave_jobs(run_id, "uk", "Other Co", ["job-key-3"])

    sent_calls: list[tuple[int, str, str]] = []

    def fake_send(user_id: int, *, title: str, body: str) -> dict:
        sent_calls.append((user_id, title, body))
        return {"sent": 1, "gone": 0, "errors": 0}

    monkeypatch.setattr(push_send, "send_user_notification", fake_send)
    monkeypatch.setattr(push_send, "vapid_configured", lambda: True)

    result = notifications_service.send_after_country_wave(country="uk", fetch_run_id=run_id)
    assert result["notified_users"] == 1
    assert len(sent_calls) == 1
    assert sent_calls[0][0] == full_id
    assert sent_calls[0][2] == "2 new jobs found!"

    again = notifications_service.send_after_country_wave(country="uk", fetch_run_id=run_id)
    assert again["skipped_claim"] >= 1
    assert len(sent_calls) == 1


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
