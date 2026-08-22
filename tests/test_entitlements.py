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
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
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
    assert body["refresh"]["synced"] is True
    assert body["refresh"]["opportunity_count"] >= 1


def test_empty_opportunity_board_does_not_rematch_every_load(client, db, seeded_catalog_v2):
    user = create_user("zeromatch", email="zeromatch@example.com", google_sub="sub-zero")
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True
    first = client.get("/api/board?country=all").get_json()
    assert first["meta"]["opportunity_count"] == 0
    from relocation_jobs.opportunities import repo as opportunities_repo

    assert opportunities_repo.needs_opportunity_bootstrap(int(user["id"])) is False
    second = client.get("/api/board?country=all").get_json()
    assert second["meta"]["opportunity_count"] == 0


def test_auth_status_includes_entitlements(auth_client, db):
    status = auth_client.get("/api/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"]["is_admin"] is True
    assert "entitlements" in status
    assert status["entitlements"]["plan"] in ("free", "full", "grandfathered")
