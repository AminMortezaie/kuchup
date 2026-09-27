from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from relocation_jobs.core.db import _utc_now
from relocation_jobs.db import init_db
from relocation_jobs.credits.service import wallet_status
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.broadcast.service import import_month_usage
from relocation_jobs.users.entitlements import entitlement_status
from relocation_jobs.core.email_confirm import decode_email_confirm_token, encode_email_confirm_token
from relocation_jobs.core.outbound_mail import send_panel_email_confirm, smtp_configured
from relocation_jobs.users.repo import (
    create_password_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_credentials_by_email,
    is_user_admin,
    login_or_register_google_user,
    password_user_needs_email_confirm,
    set_user_admin,
    set_user_email_confirmed,
    set_user_last_login_at,
    user_count,
)

_DUMMY_STAFF_HASH: str | None = None


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


def staff_logins() -> dict[str, str]:
    raw = os.environ.get("PANEL_STAFF_LOGINS", "")
    out: dict[str, str] = {}
    for part in raw.split(","):
        email, sep, hashed = part.strip().partition(":")
        email = email.strip().lower()
        hashed = hashed.strip()
        if sep and "@" in email and hashed:
            out[email] = hashed
    return out


def _dummy_staff_hash() -> str:
    global _DUMMY_STAFF_HASH
    if _DUMMY_STAFF_HASH is None:
        _DUMMY_STAFF_HASH = generate_password_hash("staff-dummy")
    return _DUMMY_STAFF_HASH


def verify_staff_credentials(identifier: str, password: str) -> str | None:
    email = identifier.strip().lower()
    logins = staff_logins()
    hashed = logins.get(email) or _dummy_staff_hash()
    if not password or not check_password_hash(hashed, password):
        return None
    return email if email in logins else None


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
        opportunities_repo.ensure_user_preferences_row(int(user["id"]))
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
        return {
            "authenticated": False,
            "allow_register": allow_register(),
        }
    user = get_user_by_id(uid)
    if not user:
        logout_user()
        return {
            "authenticated": False,
            "allow_register": allow_register(),
        }
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


def _bootstrap_signed_in_user(uid: int) -> None:
    opportunities_repo.ensure_user_preferences_row(uid)
    import_month_usage(uid)
    if opportunities_repo.needs_opportunity_bootstrap(uid):
        enqueue_user_opportunity_refresh(uid)


def _self_serve_registration_allowed() -> bool:
    return allow_register() or user_count() == 0


def _normalize_panel_email(raw: str) -> str:
    email = raw.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Valid email is required")
    return email


def _validate_panel_password(raw: str) -> None:
    if not raw or len(raw) < 8:
        raise ValueError("Password must be at least 8 characters")


def send_password_user_confirmation(*, user_id: int, email: str, base_url: str) -> None:
    if not smtp_configured():
        raise RuntimeError("Email delivery is not configured")
    token = encode_email_confirm_token(int(user_id))
    send_panel_email_confirm(to=email, token=token, base_url=base_url)


def register_with_password(email: str, password: str, *, display_name: str = "") -> dict:
    if not _self_serve_registration_allowed():
        raise ValueError("Registration is disabled")
    email = _normalize_panel_email(email)
    _validate_panel_password(password)
    existing = get_user_credentials_by_email(email)
    if existing is not None:
        if password_user_needs_email_confirm(existing):
            return {"id": int(existing["id"]), "email": email, "pending_confirmation": True}
        raise ValueError("Email already registered")
    name = (display_name or "").strip() or email.split("@", 1)[0]
    user = create_password_user(
        email=email,
        password_hash=generate_password_hash(password),
        display_name=name,
        is_admin=email in admin_emails(),
    )
    user["pending_confirmation"] = True
    return user


def confirm_email_and_login(token: str) -> dict:
    user_id = decode_email_confirm_token(token)
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Invalid confirmation link")
    creds = get_user_credentials_by_email(str(user.get("email") or ""))
    if not creds or not (creds.get("password_hash") or "").strip():
        raise ValueError("Invalid confirmation link")
    at = _utc_now()
    set_user_email_confirmed(user_id, at=at)
    set_user_last_login_at(user_id, at=at)
    user = get_user_by_id(user_id) or user
    _bootstrap_signed_in_user(int(user["id"]))
    user["last_login_at"] = at
    return user


def login_with_password(email: str, password: str) -> dict:
    email = _normalize_panel_email(email)
    if not password:
        raise ValueError("Invalid email or password")
    row = get_user_credentials_by_email(email)
    stored_hash = (row or {}).get("password_hash") or ""
    if not row or not stored_hash or not check_password_hash(stored_hash, password):
        raise ValueError("Invalid email or password")
    if password_user_needs_email_confirm(row):
        raise ValueError("Confirm your email before signing in")
    at = _utc_now()
    set_user_last_login_at(int(row["id"]), at=at)
    user = get_user_by_id(int(row["id"]))
    if not user:
        raise ValueError("Invalid email or password")
    _bootstrap_signed_in_user(int(user["id"]))
    user["last_login_at"] = at
    return user


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
    _bootstrap_signed_in_user(int(user["id"]))
    return user


def login_or_register_staff(identifier: str, password: str) -> dict:
    email = verify_staff_credentials(identifier, password)
    if not email:
        raise ValueError("Invalid staff credentials")
    user = get_user_by_email(email)
    if user is None:
        local = email.split("@", 1)[0] or "staff"
        user = create_user(
            local,
            is_admin=True,
            email=email,
            google_sub=f"staff-{email}",
            display_name=local,
        )
    elif not is_user_admin(int(user["id"])):
        set_user_admin(int(user["id"]), True)
        user = get_user_by_id(int(user["id"])) or user
    _bootstrap_signed_in_user(int(user["id"]))
    return user


def init_auth(app) -> None:
    app.secret_key = secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    secure = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
    if secure:
        app.config["SESSION_COOKIE_SECURE"] = True
    init_db()
