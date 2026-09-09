from __future__ import annotations

import pytest

from relocation_jobs.users import entitlements
from relocation_jobs.users.repo import create_user


def test_entitlement_status_free_defaults(db):
    user = create_user("freebie", email="freebie@example.com", google_sub="sub-freebie")
    status = entitlements.entitlement_status(int(user["id"]))
    assert status["plan"] == "free"
    assert status["board_company_cap"] == entitlements.free_board_company_cap()
    assert status["mcp_daily_limit"] == entitlements.free_mcp_daily_requests()
    assert status["mcp_daily_remaining"] == status["mcp_daily_limit"]
    assert status["public_job_saves_used"] == 0
    assert status["public_job_saves_remaining"] == entitlements.free_public_job_saves_per_day()


def test_set_plan_full_removes_board_cap(db):
    user = create_user("paid", email="paid@example.com", google_sub="sub-paid")
    status = entitlements.set_plan(int(user["id"]), "full")
    assert status["plan"] == "full"
    assert status["board_company_cap"] is None


def test_consume_mcp_quota_blocks_free_user(db, monkeypatch):
    monkeypatch.setenv("FREE_MCP_DAILY_REQUESTS", "2")
    user = create_user("quota", email="quota@example.com", google_sub="sub-quota")
    uid = int(user["id"])
    entitlements.consume_mcp_quota(uid)
    entitlements.consume_mcp_quota(uid)
    with pytest.raises(PermissionError, match="quota exceeded"):
        entitlements.consume_mcp_quota(uid)


def test_admin_plan_endpoint(auth_client, db, seeded_catalog_v2, monkeypatch):
    monkeypatch.setattr(
        "relocation_jobs.opportunities.service.enqueue_user_opportunity_refresh",
        lambda uid: {"queued": False, "synced": False, "type": "user", "user_id": uid},
    )
    monkeypatch.setattr(
        "relocation_jobs.web.routes.admin.enqueue_user_opportunity_refresh",
        lambda uid: {"queued": False, "synced": False, "type": "user", "user_id": uid},
    )
    user = create_user("grantme", email="grantme@example.com", google_sub="sub-grant")
    from relocation_jobs.opportunities.service import save_preferences_and_refresh

    save_preferences_and_refresh(int(user["id"]), target_countries=["uk"])
    resp = auth_client.patch(
        f"/api/admin/users/{user['id']}/plan",
        json={"plan": "grandfathered"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["entitlements"]["plan"] == "grandfathered"
    assert body["entitlements"]["board_company_cap"] is None
    assert body["refresh"]["queued"] is False


def test_empty_opportunity_board_does_not_enqueue_or_write(client, db, seeded_catalog_v2, monkeypatch):
    called = []
    monkeypatch.setattr(
        "relocation_jobs.async_jobs.enqueue.enqueue",
        lambda message: called.append(message) or {"queued": True},
    )
    user = create_user("zeromatch", email="zeromatch@example.com", google_sub="sub-zero")
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True
    first = client.get("/api/board?country=all").get_json()
    assert first["meta"]["opportunity_count"] == 0
    from relocation_jobs.broadcast import repo as broadcast_repo
    from relocation_jobs.opportunities import repo as opportunities_repo

    uid = int(user["id"])
    assert opportunities_repo.count_user_opportunities(uid) == 0
    assert opportunities_repo.get_user_preferences(uid).target_countries == ()
    assert broadcast_repo.list_assignments(uid) == []
    assert opportunities_repo.needs_opportunity_bootstrap(uid) is True
    assert called == []
    prefs = client.get("/api/preferences").get_json()["preferences"]
    assert prefs["target_countries"] == ["germany"]
    assert opportunities_repo.get_user_preferences(uid).target_countries == ()
    second = client.get("/api/board?country=all").get_json()
    assert second["meta"]["opportunity_count"] == 0
    assert called == []


def test_auth_status_includes_entitlements(auth_client, db):
    status = auth_client.get("/api/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"]["is_admin"] is True
    assert "entitlements" in status
    assert status["entitlements"]["plan"] in ("free", "full", "grandfathered")
    assert "public_job_saves_used" in status["entitlements"]
    assert status["entitlements"]["public_job_saves_remaining"] is None


def test_consume_public_job_save_three_free_then_needs_credit(db):
    user = create_user("pubsave", email="pubsave@example.com", google_sub="sub-pubsave")
    uid = int(user["id"])
    for job_id in (11, 12, 13):
        result = entitlements.consume_public_job_save(uid, job_id, f"slug-{job_id}")
        assert result["ok"] is True
        assert result["needs_credit"] is False
    fourth = entitlements.consume_public_job_save(uid, 14, "slug-14")
    assert fourth["ok"] is False
    assert fourth["needs_credit"] is True
    status = entitlements.entitlement_status(uid)
    assert status["public_job_saves_used"] == 3
    assert status["public_job_saves_remaining"] == 0


def test_consume_public_job_save_same_job_is_duplicate(db):
    user = create_user("dupsave", email="dupsave@example.com", google_sub="sub-dupsave")
    uid = int(user["id"])
    first = entitlements.consume_public_job_save(uid, 21, "same-slug")
    second = entitlements.consume_public_job_save(uid, 21, "same-slug")
    assert first["duplicate"] is False
    assert second["ok"] is True
    assert second["duplicate"] is True
    assert entitlements.entitlement_status(uid)["public_job_saves_used"] == 1


def test_consume_public_job_save_full_plan_unlimited(db):
    user = create_user("fullsave", email="fullsave@example.com", google_sub="sub-fullsave")
    uid = int(user["id"])
    entitlements.set_plan(uid, "full")
    for job_id in (31, 32, 33, 34):
        result = entitlements.consume_public_job_save(uid, job_id, f"full-{job_id}")
        assert result["ok"] is True
        assert result["needs_credit"] is False
    status = entitlements.entitlement_status(uid)
    assert status["public_job_saves_used"] == 4
    assert status["public_job_saves_remaining"] is None
