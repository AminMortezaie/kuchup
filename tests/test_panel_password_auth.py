from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from relocation_jobs.core.auth import login_with_password, register_with_password
from relocation_jobs.core.email_confirm import encode_email_confirm_token
from relocation_jobs.users.repo import (
    create_password_user,
    get_user_by_email,
    get_user_credentials_by_email,
    password_user_needs_email_confirm,
    set_user_email_confirmed,
)


@pytest.fixture
def _quiet_bootstrap(monkeypatch):
    monkeypatch.setattr(
        "relocation_jobs.core.auth.enqueue_user_opportunity_refresh",
        lambda uid: {"queued": False, "synced": False, "user_id": uid},
    )


@pytest.fixture
def _brevo_ready(monkeypatch):
    monkeypatch.setattr("relocation_jobs.core.auth.brevo_configured", lambda: True)
    sent: dict = {}

    def _capture(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("relocation_jobs.core.auth.send_panel_email_confirm", _capture)
    return sent


def test_register_sends_confirm_and_is_not_authenticated(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "panel-user@example.com"
    password = "secret-pass-1"
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["authenticated"] is False
    assert body["confirm_email_sent"] is True
    assert body["email"] == email
    assert _brevo_ready["to"] == email
    assert _brevo_ready["token"]

    status = client.get("/api/auth/status").get_json()
    assert status["authenticated"] is False


def test_confirm_email_logs_in(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "confirm-me@example.com"
    password = "secret-pass-1"
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = _brevo_ready["token"]
    res = client.get(f"/api/auth/confirm-email?token={token}")
    assert res.status_code in (302, 303)
    assert "/panel" in (res.headers.get("Location") or "")
    status = client.get("/api/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"]["email"] == email

    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is True


def test_login_before_confirm_is_blocked(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "unconfirmed@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret-pass-1"},
    )
    res = client.post("/api/auth/login", json={"email": email, "password": "secret-pass-1"})
    assert res.status_code == 403
    assert "confirm your email" in res.get_json()["error"].lower()


def test_login_wrong_password(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "wrong-pass@example.com"
    user = create_password_user(
        email=email,
        password_hash=generate_password_hash("correct-password"),
    )
    set_user_email_confirmed(int(user["id"]))
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "Invalid email or password"


def test_register_duplicate_email(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "dup@example.com"
    user = create_password_user(
        email=email,
        password_hash=generate_password_hash("first-password"),
    )
    set_user_email_confirmed(int(user["id"]))
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "another-pass"},
    )
    assert res.status_code == 409
    assert "already exists" in res.get_json()["error"].lower()


def test_register_respects_allow_register(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "0")
    res = client.post(
        "/api/auth/register",
        json={"email": "blocked@example.com", "password": "long-enough"},
    )
    assert res.status_code == 403


def test_panel_login_does_not_use_staff_endpoint(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    staff_email = "staff-only@example.com"
    staff_hash = generate_password_hash("staff-secret")
    monkeypatch.setenv("PANEL_STAFF_LOGINS", f"{staff_email}:{staff_hash}")
    user = create_password_user(
        email=staff_email,
        password_hash=generate_password_hash("panel-secret"),
    )
    set_user_email_confirmed(int(user["id"]))
    res = client.post(
        "/api/auth/login",
        json={"email": staff_email, "password": "panel-secret"},
    )
    assert res.status_code == 200
    assert res.get_json()["user"]["is_admin"] is False

    staff_res = client.post(
        "/api/auth/staff",
        json={"email": staff_email, "password": "staff-secret"},
    )
    assert staff_res.status_code == 200
    assert staff_res.get_json()["user"]["is_admin"] is True


def test_register_with_password_service(db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    user = register_with_password("service@example.com", "service-pass")
    assert user["email"] == "service@example.com"
    creds = get_user_credentials_by_email("service@example.com")
    assert creds and creds["password_hash"]
    assert password_user_needs_email_confirm(creds)
    set_user_email_confirmed(int(user["id"]))
    again = login_with_password("service@example.com", "service-pass")
    assert again["id"] == user["id"]
    assert get_user_by_email("service@example.com") is not None


def test_google_still_works_after_password_auth(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    monkeypatch.setattr(
        "relocation_jobs.web.routes.auth.profile_from_authorization_code",
        lambda **_: {
            "google_sub": "sub-still-google",
            "email": "google-still@example.com",
            "display_name": "Google User",
        },
    )
    from relocation_jobs.core.google_oauth import encode_oauth_state

    state = encode_oauth_state(
        next="/panel",
        mcp_request_id="",
        redirect_uri="http://localhost/api/auth/google/callback",
    )
    res = client.get(f"/api/auth/google/callback?code=ok&state={state}")
    assert res.status_code in (302, 303)
    status = client.get("/api/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"]["email"] == "google-still@example.com"


def test_register_send_failure_removes_new_user(client, db, monkeypatch, _quiet_bootstrap, _brevo_ready):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "rollback@example.com"

    def _fail(**kwargs):
        raise RuntimeError("Brevo send failed")

    monkeypatch.setattr("relocation_jobs.core.auth.send_panel_email_confirm", _fail)
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret-pass-1"},
    )
    assert res.status_code == 503
    assert get_user_by_email(email) is None


def test_confirm_with_direct_token(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    user = create_password_user(
        email="token@example.com",
        password_hash=generate_password_hash("secret-pass-1"),
    )
    token = encode_email_confirm_token(int(user["id"]))
    res = client.get(f"/api/auth/confirm-email?token={token}")
    assert res.status_code in (302, 303)
    assert client.get("/api/auth/status").get_json()["authenticated"] is True
