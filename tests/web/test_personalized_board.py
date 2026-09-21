from __future__ import annotations

from relocation_jobs.broadcast import repo as broadcast_repo
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.users.repo import create_user
from tests.helpers.seed import seed_free_assignments


def _login_as(client, user: dict) -> None:
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True


def _assert_no_country_preference_meta(meta: dict) -> None:
    assert "needs_preferences" not in meta
    assert "target_countries" not in meta


def test_preferences_api_removed(client, db, seeded_catalog_v2):
    user = create_user("noprefs", email="noprefs@example.com", google_sub="sub-no-prefs")
    _login_as(client, user)
    assert client.get("/api/preferences").status_code == 404
    put = client.put("/api/preferences", json={"target_countries": ["uk"]})
    assert put.status_code in (404, 405)


def test_free_user_board_not_country_gated(client, db, seeded_catalog_v2):
    user = create_user("freeall", email="freeall@example.com", google_sub="sub-free-all")
    seed_free_assignments(int(user["id"]), ["uk"])
    _login_as(client, user)
    resp = client.get("/api/board?country=all")
    assert resp.status_code == 200
    payload = resp.get_json()
    _assert_no_country_preference_meta(payload["meta"])
    assert payload["meta"]["plan"] == "free"
    countries = {company["country"] for company in payload["companies"]}
    assert "uk" in countries


def test_free_user_board_filters_to_opportunities(client, db, seeded_catalog_v2):
    user = create_user("freefilter", email="freefilter@example.com", google_sub="sub-free-filter")
    seed_free_assignments(int(user["id"]), ["uk"])
    _login_as(client, user)
    resp = client.get("/api/board?country=uk")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["companies"]) >= 1
    _assert_no_country_preference_meta(payload["meta"])
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
    _assert_no_country_preference_meta(payload["meta"])
    assert payload["meta"]["opportunity_count"] is None
    assert payload["meta"]["upgrade_available"] is False


def test_new_free_user_without_assignments(client, db, seeded_catalog_v2):
    user = create_user("freedefault", email="freedefault@example.com", google_sub="sub-free-default")
    _login_as(client, user)
    resp = client.get("/api/board?country=all")
    assert resp.status_code == 200
    payload = resp.get_json()
    _assert_no_country_preference_meta(payload["meta"])
    uid = int(user["id"])
    assert opportunities_repo.count_user_opportunities(uid) == 0
    assert broadcast_repo.list_assignments(uid) == []
