from __future__ import annotations

from relocation_jobs.opportunities.service import save_preferences_and_refresh
from relocation_jobs.users.repo import create_user


def _login_as(client, user: dict) -> None:
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True


def test_free_user_defaults_to_germany(client, db, seeded_catalog_v2):
    user = create_user("freedefault", email="freedefault@example.com", google_sub="sub-free-default")
    _login_as(client, user)
    resp = client.get("/api/board?country=all")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["needs_preferences"] is True
    assert payload["meta"]["target_countries"] == ["germany"]
    assert payload["meta"]["plan"] == "free"
    # This suite shares catalog rows across tests; the default must never leak
    # the UK fixture even if another test has already seeded Germany.
    assert all(company["country"] == "germany" for company in payload["companies"])

    prefs = client.get("/api/preferences").get_json()["preferences"]
    assert prefs["target_countries"] == ["germany"]
    assert prefs["preferences_confirmed"] is False


def test_free_user_board_filters_to_opportunities(client, db, seeded_catalog_v2):
    user = create_user("freefilter", email="freefilter@example.com", google_sub="sub-free-filter")
    save_preferences_and_refresh(int(user["id"]), target_countries=["uk"])
    _login_as(client, user)
    resp = client.get("/api/board?country=uk")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["companies"]) >= 1
    assert payload["meta"]["needs_preferences"] is False
    assert payload["meta"]["opportunity_count"] >= 1
    assert payload["meta"]["positions_used"] == 0
    assert payload["meta"]["positions_budget"] == 30
    assert payload["meta"]["jobs_per_company_peek"] == 3
    assert all(len(company.get("jobs") or []) <= 3 for company in payload["companies"])
    assert all(c["name"] for c in payload["companies"])


def test_admin_board_bypasses_opportunity_filter(v2_auth_client, seeded_catalog_v2):
    resp = v2_auth_client.get("/api/board?country=uk")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["companies"]) == 1
    assert payload["meta"]["needs_preferences"] is False
    assert payload["meta"]["opportunity_count"] is None
    assert payload["meta"]["upgrade_available"] is False


def test_preferences_put_refreshes_opportunities(client, db, seeded_catalog_v2, monkeypatch):
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
    user = create_user("prefuser", email="prefuser@example.com", google_sub="sub-pref")
    _login_as(client, user)
    put = client.put(
        "/api/preferences",
        json={"target_countries": ["uk"]},
    )
    assert put.status_code == 200
    body = put.get_json()
    assert body["ok"] is True
    assert body["preferences"]["target_countries"] == ["uk"]
    assert body["refresh"]["synced"] is True
    assert body["refresh"]["opportunity_count"] >= 1

    get = client.get("/api/preferences")
    assert get.status_code == 200
    assert get.get_json()["preferences"]["target_countries"] == ["uk"]

    board = client.get("/api/board?country=uk").get_json()
    assert board["meta"]["needs_preferences"] is False
    assert board["meta"]["opportunity_count"] >= 1
    assert len(board["companies"]) >= 1
