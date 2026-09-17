from __future__ import annotations

from datetime import datetime, timedelta, timezone

from relocation_jobs.admin.service import get_activation_metrics
from relocation_jobs.core.db import db_transaction
from relocation_jobs.credits import repo as credits_repo
from relocation_jobs.mcp import repo as mcp_repo
from relocation_jobs.mcp.oauth_repo import create_api_token
from relocation_jobs.payments.types import ORDER_KIND_CREDITS, ORDER_KIND_FULL_ACCESS
from relocation_jobs.positions import repo as positions_repo
from relocation_jobs.users.repo import (
    create_user,
    get_user_by_username,
    update_user_mcp_quota,
    update_user_plan,
)


def _user(name: str, **kwargs) -> dict:
    return create_user(
        name,
        email=f"{name}@example.com",
        google_sub=f"sub-{name}",
        **kwargs,
    )


def _set_created(user_id: int, created_at: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            "UPDATE users SET created_at = %s WHERE id = %s",
            (created_at, user_id),
        )


def _set_last_login(user_id: int, last_login_at: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = %s WHERE id = %s",
            (last_login_at, user_id),
        )


def _step(payload: dict, key: str) -> dict:
    return next(row for row in payload["activation"] if row["key"] == key)


def _activity(payload: dict, key: str) -> dict:
    return next(row for row in payload["latest_activity"] if row["key"] == key)


def _reset_admin_quota() -> None:
    admin = get_user_by_username("admin")
    update_user_mcp_quota(int(admin["id"]), quota_date="", quota_used=0)


def test_activation_metrics_requires_auth(client, db):
    assert client.get("/api/admin/activation-metrics").status_code == 401


def test_activation_metrics_requires_admin(client, db):
    user = _user("act-regular")
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
    resp = client.get("/api/admin/activation-metrics")
    assert resp.status_code == 403


def test_activation_metrics_counts_real_signals_and_subsequent_login(v2_auth_client, db):
    _reset_admin_quota()
    tracker = _user("act-track")
    workspace = _user("act-workspace")
    mcp_user = _user("act-mcp")
    credits = _user("act-credits")
    full = _user("act-full")
    idle_full = _user("act-idle-full", plan="full")
    grandpa = _user("act-grandpa", plan="grandfathered")

    last_week = (datetime.now(timezone.utc) - timedelta(days=8)).replace(microsecond=0)
    returned_at = datetime.now(timezone.utc).replace(microsecond=0)
    _set_created(int(tracker["id"]), last_week.isoformat())
    _set_last_login(int(tracker["id"]), returned_at.isoformat())
    _set_last_login(int(grandpa["id"]), grandpa["created_at"])

    positions_repo.set_looking_to_apply(
        int(tracker["id"]),
        "uk",
        "Acme",
        "https://jobs.example/track",
        True,
        job_title="Backend",
    )
    mcp_repo.upsert_application_shell(
        int(workspace["id"]),
        "uk:acme:https://jobs.example/ws",
        country="uk",
        company="Acme",
        url="https://jobs.example/ws",
    )
    create_api_token(user_id=int(mcp_user["id"]), label="cursor")
    update_user_mcp_quota(int(mcp_user["id"]), quota_date="2026-09-17", quota_used=2)

    credit_order = credits_repo.create_order(
        int(credits["id"]),
        pack_key="starter",
        credits=50,
        price_minor=499,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_CREDITS,
    )
    credits_repo.update_order_checkout(
        credit_order,
        provider_order_id="act-credits-inv",
        checkout_url="https://example.com/pay",
    )
    pending = credits_repo.create_order(
        int(credits["id"]),
        pack_key="mini",
        credits=10,
        price_minor=99,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_CREDITS,
    )
    credits_repo.update_order_checkout(
        pending,
        provider_order_id="act-credits-pending",
        checkout_url="https://example.com/pay-pending",
    )
    credits_repo.mark_order_paid("nowpayments", "act-credits-inv")

    full_order = credits_repo.create_order(
        int(full["id"]),
        pack_key="full_access",
        credits=0,
        price_minor=2900,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_FULL_ACCESS,
    )
    credits_repo.update_order_checkout(
        full_order,
        provider_order_id="act-full-inv",
        checkout_url="https://example.com/full",
    )
    credits_repo.mark_order_paid("nowpayments", "act-full-inv")
    update_user_plan(int(full["id"]), "full")
    update_user_plan(int(idle_full["id"]), "full")

    payload = v2_auth_client.get("/api/admin/activation-metrics").get_json()
    assert payload["total_users"] == 8
    assert payload["plans"] == {"free": 5, "full": 2, "grandfathered": 1}

    login = _step(payload, "subsequent_login")
    assert login["available"] is True
    assert login["count"] == 1
    assert "last_login_at" in login["definition"]

    assert _step(payload, "job_track")["available"] is True
    assert _step(payload, "job_track")["count"] == 1
    assert _step(payload, "workspace")["count"] == 1
    assert _step(payload, "mcp")["count"] == 1
    assert _step(payload, "credit_purchase")["count"] == 1
    assert _step(payload, "full_purchase")["count"] == 1

    last_week_key = (last_week.date() - timedelta(days=last_week.weekday())).isoformat()
    by_week = {row["week_start"]: row["signups"] for row in payload["signup_cohorts"]}
    assert by_week[last_week_key] == 1
    assert payload["signups_this_week"] == payload["total_users"] - 1

    assert _activity(payload, "subsequent_login")["available"] is True
    assert _activity(payload, "subsequent_login")["username"] == "act-track"
    assert _activity(payload, "subsequent_login")["at"]
    assert _activity(payload, "job_track")["username"] == "act-track"
    assert _activity(payload, "workspace")["username"] == "act-workspace"
    assert _activity(payload, "mcp")["username"] == "act-mcp"
    assert _activity(payload, "credit_purchase")["username"] == "act-credits"
    assert _activity(payload, "full_purchase")["username"] == "act-full"
    assert _activity(payload, "signup")["at"]


def test_activation_metrics_service_matches_http(v2_auth_client, db):
    _reset_admin_quota()
    http = v2_auth_client.get("/api/admin/activation-metrics").get_json()
    assert http == get_activation_metrics()
    dashboard = v2_auth_client.get("/api/admin/dashboard").get_json()
    assert dashboard["panel_stats"] is None
    assert "activation" not in dashboard
