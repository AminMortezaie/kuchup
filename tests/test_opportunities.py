from __future__ import annotations

from relocation_jobs.async_jobs.dispatch import process_message
from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.opportunities.matcher import match_opportunities
from relocation_jobs.opportunities.service import save_preferences_and_refresh
from relocation_jobs.opportunities.types import CompanyCandidate, MatchInput, UserPreferences
from relocation_jobs.users.repo import create_user


def test_matcher_applies_free_cap():
    prefs = UserPreferences(user_id=1, target_countries=("uk",))
    candidates = tuple(
        CompanyCandidate(
            country="uk",
            company_name=f"Co{i}",
            newest_fetched=f"2026-01-{i:02d}",
            open_job_count=1,
        )
        for i in range(1, 6)
    )
    rows = match_opportunities(
        MatchInput(
            plan="free",
            is_admin=False,
            preferences=prefs,
            board_company_cap=2,
            candidates=candidates,
        )
    )
    assert len(rows) == 2
    assert rows[0].company_name == "Co5"
    assert rows[1].company_name == "Co4"


def test_matcher_skips_empty_companies():
    prefs = UserPreferences(user_id=1, target_countries=("uk",))
    candidates = (
        CompanyCandidate(country="uk", company_name="Empty", newest_fetched="2026-02-01", open_job_count=0),
        CompanyCandidate(country="uk", company_name="Open", newest_fetched="2026-01-01", open_job_count=2),
    )
    rows = match_opportunities(
        MatchInput(
            plan="free",
            is_admin=False,
            preferences=prefs,
            board_company_cap=10,
            candidates=candidates,
        )
    )
    assert [r.company_name for r in rows] == ["Open"]


def test_matcher_requires_target_countries():
    rows = match_opportunities(
        MatchInput(
            plan="full",
            is_admin=False,
            preferences=UserPreferences(user_id=1),
            board_company_cap=None,
            candidates=(CompanyCandidate(country="uk", company_name="Acme", open_job_count=1),),
        )
    )
    assert rows == []


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
