from __future__ import annotations

from pathlib import Path

from werkzeug.security import generate_password_hash

from relocation_jobs.core.paths import STATIC_DIR
from relocation_jobs.users.repo import get_user_by_email, user_count

STAFF_EMAIL = "kio@example.com"
STAFF_PASSWORD = "staff-secret-ok"
STAFF_HASH = generate_password_hash(STAFF_PASSWORD)


def _quiet_refresh(monkeypatch):
    monkeypatch.setattr(
        "relocation_jobs.core.auth.enqueue_user_opportunity_refresh",
        lambda uid: {"queued": False, "synced": False, "user_id": uid},
    )


def _set_staff_logins(monkeypatch, mapping: dict[str, str] | None = None):
    mapping = mapping if mapping is not None else {STAFF_EMAIL: STAFF_HASH}
    raw = ",".join(f"{email}:{hashed}" for email, hashed in mapping.items())
    monkeypatch.setenv("PANEL_STAFF_LOGINS", raw)


def test_staff_login_creates_admin_and_sets_session(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    before = user_count()
    resp = client.post(
        "/api/auth/staff",
        json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == STAFF_EMAIL
    assert body["user"]["is_admin"] is True
    assert user_count() == before + 1
    status = client.get("/api/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"]["is_admin"] is True
    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200


def test_staff_login_accepts_local_part_identifier(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    resp = client.post(
        "/api/auth/staff",
        json={"email": "kio", "password": STAFF_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == STAFF_EMAIL


def test_staff_login_rejects_wrong_password(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    before = user_count()
    resp = client.post(
        "/api/auth/staff",
        json={"email": STAFF_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid email or password"
    assert get_user_by_email(STAFF_EMAIL) is None
    assert user_count() == before
    assert client.get("/api/auth/status").get_json()["authenticated"] is False
    assert client.get("/api/admin/dashboard").status_code == 401


def test_staff_login_rejects_missing_fields(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    resp = client.post("/api/auth/staff", json={"email": STAFF_EMAIL})
    assert resp.status_code == 400
    assert client.get("/api/auth/status").get_json()["authenticated"] is False


def test_staff_login_rejects_unknown_email(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    resp = client.post(
        "/api/auth/staff",
        json={"email": "figo@example.com", "password": STAFF_PASSWORD},
    )
    assert resp.status_code == 401
    assert get_user_by_email("figo@example.com") is None
    assert client.get("/api/admin/dashboard").status_code == 401


def test_staff_login_rejects_when_unset(client, db, monkeypatch):
    _quiet_refresh(monkeypatch)
    monkeypatch.delenv("PANEL_STAFF_LOGINS", raising=False)
    resp = client.post(
        "/api/auth/staff",
        json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid email or password"
    status = client.get("/api/auth/status").get_json()
    assert status["staff_login"] is False
    assert status["authenticated"] is False


def test_staff_login_does_not_break_google_admin(client, db, monkeypatch):
    from relocation_jobs.core.google_oauth import encode_oauth_state

    _quiet_refresh(monkeypatch)
    _set_staff_logins(monkeypatch)
    monkeypatch.setenv("PANEL_ALLOW_REGISTER", "1")
    monkeypatch.setenv("PANEL_ADMIN_EMAILS", "amin@example.com")

    def fake_profile(*, code: str, redirect_uri: str):
        return {
            "google_sub": "sub-amin",
            "email": "amin@example.com",
            "display_name": "Amin",
        }

    monkeypatch.setattr(
        "relocation_jobs.web.routes.auth.profile_from_authorization_code",
        fake_profile,
    )
    state = encode_oauth_state(
        next="/admin",
        mcp_request_id="",
        redirect_uri="http://localhost/api/auth/google/callback",
    )
    resp = client.get(f"/api/auth/google/callback?code=ok-code&state={state}")
    assert resp.status_code in (302, 303)
    body = client.get("/api/auth/status").get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "amin@example.com"
    assert body["user"]["is_admin"] is True
    assert body["staff_login"] is True


def test_admin_login_is_not_public_seo(client):
    html = (Path(STATIC_DIR) / "admin.html").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex, nofollow"' in html
    assert 'id="adminStaffLoginForm"' in html
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "noindex" in (resp.headers.get("X-Robots-Tag") or "")
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin" in robots
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/admin</loc>" not in sitemap
    assert "https://kuchup.com/admin" not in sitemap
