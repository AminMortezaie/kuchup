from __future__ import annotations

from relocation_jobs.async_jobs.dispatch import process_message
from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.opportunities.service import save_preferences_and_refresh
from relocation_jobs.users.repo import create_user


def test_refresh_user_opportunities_from_catalog(db, seeded_catalog_v2, monkeypatch):
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
    user = create_user("oppuser", email="oppuser@example.com", google_sub="sub-opp")
    result = save_preferences_and_refresh(int(user["id"]), target_countries=["uk"])
    assert result["refresh"]["synced"] is True
    assert result["refresh"]["opportunity_count"] >= 1
    assert "uk" in result["preferences"]["target_countries"]


def test_process_user_message(db, seeded_catalog_v2, monkeypatch):
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
    user = create_user("msguser", email="msguser@example.com", google_sub="sub-msg")
    save_preferences_and_refresh(int(user["id"]), target_countries=["uk"])
    out = process_message({"type": "user", "user_id": int(user["id"])})
    assert out["opportunity_count"] >= 1


def test_enqueue_without_sqs_syncs(db, seeded_catalog_v2, monkeypatch):
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
    user = create_user("syncuser", email="syncuser@example.com", google_sub="sub-sync")
    save_preferences_and_refresh(int(user["id"]), target_countries=["uk"])
    result = enqueue_user_opportunity_refresh(int(user["id"]))
    assert result["queued"] is False
    assert result["synced"] is True
    assert result["opportunity_count"] >= 1
