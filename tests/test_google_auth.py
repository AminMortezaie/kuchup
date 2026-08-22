from __future__ import annotations

import pytest

from relocation_jobs.core.auth import login_or_register_google
from relocation_jobs.core.google_oauth import decode_oauth_state, encode_oauth_state
from relocation_jobs.users.repo import get_user_by_email, get_user_by_google_sub, user_count


def test_oauth_state_roundtrip():
    state = encode_oauth_state(next="/panel", mcp_request_id="")
    payload = decode_oauth_state(state)
    assert payload["next"] == "/panel"
    assert "nonce" in payload
    assert "exp" in payload


def test_login_or_register_google_creates_and_promotes_admin(db, monkeypatch):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    monkeypatch.setenv("PANEL_ADMIN_EMAILS", "owner@example.com")
    before = user_count()
    user = login_or_register_google(
        {
            "google_sub": "sub-owner-1",
            "email": "owner@example.com",
            "display_name": "Owner",
        }
    )
    assert user["email"] == "owner@example.com"
    assert user["is_admin"] is True
    assert user["plan"] == "free"
    assert user_count() == before + 1
    again = login_or_register_google(
        {
            "google_sub": "sub-owner-1",
            "email": "owner@example.com",
            "display_name": "Owner",
        }
    )
    assert again["id"] == user["id"]
    assert get_user_by_google_sub("sub-owner-1")["id"] == user["id"]


def test_login_or_register_google_respects_allow_register(db, monkeypatch):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "0")
    monkeypatch.setenv("PANEL_ADMIN_EMAILS", "")
    assert user_count() > 0
    with pytest.raises(ValueError, match="Registration is disabled"):
        login_or_register_google(
            {
                "google_sub": "sub-blocked",
                "email": "blocked@example.com",
                "display_name": "Blocked",
            }
        )
    assert get_user_by_email("blocked@example.com") is None


def test_google_callback_sets_session(client, db, monkeypatch):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    monkeypatch.setenv("PANEL_ADMIN_EMAILS", "")

    def fake_profile(*, code: str, redirect_uri: str):
        assert code == "ok-code"
        return {
            "google_sub": "sub-callback",
            "email": "callback@example.com",
            "display_name": "Callback User",
        }

    monkeypatch.setattr(
        "relocation_jobs.web.routes.auth.profile_from_authorization_code",
        fake_profile,
    )
    state = encode_oauth_state(
        next="/panel",
        mcp_request_id="",
        redirect_uri="http://localhost/api/auth/google/callback",
    )
    resp = client.get(f"/api/auth/google/callback?code=ok-code&state={state}")
    assert resp.status_code in (302, 303)
    assert "/panel" in (resp.headers.get("Location") or "")
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    body = status.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "callback@example.com"
    assert body["user"]["is_admin"] is False
