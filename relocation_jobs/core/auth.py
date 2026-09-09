from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import g, jsonify, request, session

from relocation_jobs.db import init_db
from relocation_jobs.credits.service import wallet_status
from relocation_jobs.opportunities.service import ensure_default_preferences
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.broadcast.service import import_month_usage
from relocation_jobs.users.entitlements import entitlement_status
from relocation_jobs.users.repo import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    is_user_admin,
    login_or_register_google_user,
    set_user_admin,
    user_count,
)


def secret_key() -> str:
    key = os.environ.get("PANEL_SECRET_KEY", "").strip()
    if key:
        return key
    return secrets.token_hex(32)


def allow_register() -> bool:
    return os.environ.get("PANEL_ALLOW_REGISTER", "").lower() in ("1", "true", "yes")


def admin_emails() -> set[str]:
    raw = os.environ.get("PANEL_ADMIN_EMAILS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def auth_disabled() -> bool:
    if os.environ.get("PANEL_AUTH_DISABLED", "").lower() not in ("1", "true", "yes"):
        return False
    host = request.host.split(":")[0].lower()
    return host in ("127.0.0.1", "localhost")


def ensure_dev_login() -> None:
    if not auth_disabled() or current_user_id():
        return
    raw = os.environ.get("PANEL_ADMIN_EMAILS", "")
    email = next((part.strip().lower() for part in raw.split(",") if part.strip()), "admin@localhost")
    user = get_user_by_email(email)
    if user is None:
        user = create_user(
            email.split("@", 1)[0] or "admin",
            is_admin=True,
            email=email,
            google_sub=f"local-dev-{email}",
        )
        ensure_default_preferences(int(user["id"]))
        import_month_usage(int(user["id"]))
        enqueue_user_opportunity_refresh(int(user["id"]))
    elif not is_user_admin(int(user["id"])):
        set_user_admin(int(user["id"]), True)
        user = get_user_by_id(int(user["id"])) or user
    login_user(int(user["id"]), user["username"])


def login_user(user_id: int, username: str) -> None:
    session.clear()
    session["user_id"] = user_id
    session["username"] = username
    session.permanent = True


def logout_user() -> None:
    session.clear()


def current_user_id() -> int | None:
    uid = session.get("user_id")
    return int(uid) if uid is not None else None


def current_username() -> str | None:
    return session.get("username")


def auth_status() -> dict:
    ensure_dev_login()
    uid = current_user_id()
    if not uid:
        return {"authenticated": False, "allow_register": allow_register()}
    user = get_user_by_id(uid)
    if not user:
        logout_user()
        return {"authenticated": False, "allow_register": allow_register()}
    return {
        "authenticated": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email") or "",
            "display_name": user.get("display_name") or "",
            "is_admin": is_user_admin(user["id"]),
            "plan": user.get("plan") or "free",
        },
        "entitlements": entitlement_status(uid),
        "credits": wallet_status(uid),
        "allow_register": allow_register(),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        ensure_dev_login()
        uid = current_user_id()
        if not uid or not get_user_by_id(uid):
            logout_user()
            return jsonify({"error": "Authentication required"}), 401
        g.user_id = uid
        g.username = current_username()
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_user_admin(g.user_id):
            return jsonify({"error": "Admin access required"}), 403
        return view(*args, **kwargs)

    return wrapped


def login_or_register_google(profile: dict) -> dict:
    email = (profile.get("email") or "").strip().lower()
    google_sub = (profile.get("google_sub") or "").strip()
    display_name = (profile.get("display_name") or "").strip()
    if not email or not google_sub:
        raise ValueError("Google profile incomplete")
    user = login_or_register_google_user(
        google_sub=google_sub,
        email=email,
        display_name=display_name,
        allow_new=allow_register() or user_count() == 0,
        is_admin=email in admin_emails(),
    )
    uid = int(user["id"])
    ensure_default_preferences(uid)
    import_month_usage(uid)
    if opportunities_repo.needs_opportunity_bootstrap(uid):
        enqueue_user_opportunity_refresh(uid)
    return user


def init_auth(app) -> None:
    app.secret_key = secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    secure = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
    if secure:
        app.config["SESSION_COOKIE_SECURE"] = True
    init_db()
