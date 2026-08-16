from __future__ import annotations

import os
from urllib.parse import urlencode

from flask import jsonify, redirect, request

from relocation_jobs.core.auth import auth_status, login_or_register_google, login_user, logout_user
from relocation_jobs.core.google_oauth import (
    build_authorize_url,
    decode_oauth_state,
    encode_oauth_state,
    google_configured,
    profile_from_authorization_code,
)
from relocation_jobs.mcp.oauth_provider import complete_login_redirect, public_base_url


def _panel_redirect_uri() -> str:
    configured = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return f"{request.url_root.rstrip('/')}/api/auth/google/callback"


def _safe_next_path(raw: str | None) -> str:
    value = (raw or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    return "/panel"


_USER_SAFE_OAUTH_ERRORS = {
    "registration is disabled": "New sign-ups are closed right now. Ask for an invite or try again later.",
    "oauth state expired": "Sign-in timed out — try again.",
    "invalid oauth state signature": "Sign-in could not be verified — try again.",
    "google token exchange failed": "We could not complete Google sign-in — try again.",
    "google sign-in is not configured": "Google sign-in is temporarily unavailable.",
}


def _user_safe_oauth_error(exc: BaseException) -> str:
    raw = (str(exc) or "Google sign-in failed").strip()
    mapped = _USER_SAFE_OAUTH_ERRORS.get(raw.lower())
    if mapped:
        return mapped
    if "registration" in raw.lower() and "disabled" in raw.lower():
        return _USER_SAFE_OAUTH_ERRORS["registration is disabled"]
    return "Google sign-in failed — try again."


def _login_error_redirect(message: str, *, next_path: str = "/panel"):
    query = urlencode({"error": message})
    target = next_path if next_path.startswith("/") else "/panel"
    sep = "&" if "?" in target else "?"
    return redirect(f"{target}{sep}{query}")


def register(app):
    @app.get("/api/auth/status")
    def api_auth_status():
        return jsonify(auth_status())

    @app.post("/api/auth/logout")
    def api_auth_logout():
        logout_user()
        return jsonify({"ok": True, "authenticated": False})

    @app.get("/api/auth/google")
    def api_auth_google_start():
        next_path = _safe_next_path(request.args.get("next"))
        if not google_configured():
            return _login_error_redirect(
                "Google sign-in is temporarily unavailable.",
                next_path=next_path,
            )
        mcp_request_id = (request.args.get("mcp_request_id") or "").strip()
        redirect_uri = _panel_redirect_uri()
        state = encode_oauth_state(
            next=next_path,
            mcp_request_id=mcp_request_id,
            redirect_uri=redirect_uri,
        )
        return redirect(build_authorize_url(redirect_uri=redirect_uri, state=state))

    @app.get("/api/auth/google/callback")
    def api_auth_google_callback():
        err = (request.args.get("error") or "").strip()
        state_raw = (request.args.get("state") or "").strip()
        next_path = "/panel"
        if state_raw:
            try:
                next_path = _safe_next_path(decode_oauth_state(state_raw).get("next"))
            except (ValueError, RuntimeError):
                next_path = "/panel"
        if err:
            return _login_error_redirect("Google sign-in was cancelled", next_path=next_path)
        code = (request.args.get("code") or "").strip()
        if not code or not state_raw:
            return _login_error_redirect("Missing Google authorization code", next_path=next_path)
        try:
            state = decode_oauth_state(state_raw)
            next_path = _safe_next_path(state.get("next"))
            redirect_uri = (state.get("redirect_uri") or _panel_redirect_uri()).strip()
            profile = profile_from_authorization_code(code=code, redirect_uri=redirect_uri)
            user = login_or_register_google(profile)
            login_user(user["id"], user["username"])
        except (ValueError, RuntimeError) as exc:
            return _login_error_redirect(_user_safe_oauth_error(exc), next_path=next_path)

        mcp_request_id = (state.get("mcp_request_id") or "").strip()
        if mcp_request_id:
            try:
                redirect_url = complete_login_redirect(
                    request_id=mcp_request_id,
                    user_id=int(user["id"]),
                )
                if redirect_url.startswith("/"):
                    redirect_url = f"{public_base_url()}{redirect_url}"
                return redirect(redirect_url)
            except Exception:
                return _login_error_redirect(
                    "MCP authorization expired — start again from Claude or Cursor",
                    next_path=next_path,
                )

        return redirect(next_path)
