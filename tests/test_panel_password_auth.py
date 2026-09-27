from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from relocation_jobs.core.auth import login_with_password, register_with_password
from relocation_jobs.users.repo import create_password_user, get_user_by_email, get_user_credentials_by_email


@pytest.fixture
def _quiet_bootstrap(monkeypatch):
    monkeypatch.setattr(
        "relocation_jobs.core.auth.enqueue_user_opportunity_refresh",
        lambda uid: {"queued": False, "synced": False, "user_id": uid},
    )


def test_register_and_login_with_password(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "panel-user@example.com"
    password = "secret-pass-1"
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == email
    assert body["user"]["is_admin"] is False

    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is True
    assert res.get_json()["user"]["email"] == email


def test_login_wrong_password(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "wrong-pass@example.com"
    create_password_user(
        email=email,
        password_hash=generate_password_hash("correct-password"),
    )
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "Invalid email or password"


def test_register_duplicate_email(client, db, monkeypatch, _quiet_bootstrap):
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    email = "dup@example.com"
    create_password_user(
        email=email,
        password_hash=generate_password_hash("first-password"),
    )
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "another-pass"},
    )
    assert res.status_code == 409
    assert "already exists" in res.get_json()["error"].lower()


def test_register_respects_allow_register(client, db, monkeypatch, _quiet_bootstrap):
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
    create_password_user(
        email=staff_email,
        password_hash=generate_password_hash("panel-secret"),
    )
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
    again = login_with_password("service@example.com", "service-pass")
    assert again["id"] == user["id"]
    assert get_user_by_email("service@example.com") is not None
