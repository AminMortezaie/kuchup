from __future__ import annotations

import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from typing import Any
from urllib.parse import urlencode

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_STATE_TTL_SECONDS = 600
_SCOPES = "openid email profile"


def google_client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def google_client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def google_configured() -> bool:
    return bool(google_client_id() and google_client_secret())


def _state_secret() -> bytes:
    raw = os.environ.get("PANEL_SECRET_KEY", "").strip() or "dev-google-oauth-state"
    return raw.encode()


def encode_oauth_state(**fields: Any) -> str:
    payload = {**fields, "nonce": secrets.token_urlsafe(8), "exp": int(time.time()) + _STATE_TTL_SECONDS}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac_new(_state_secret(), raw, sha256).hexdigest()
    return f"{urlsafe_b64encode(raw).decode().rstrip('=')}.{sig}"


def decode_oauth_state(state: str) -> dict[str, Any]:
    try:
        blob, sig = state.rsplit(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid OAuth state") from exc
    pad = "=" * (-len(blob) % 4)
    raw = urlsafe_b64decode(blob + pad)
    expected = hmac_new(_state_secret(), raw, sha256).hexdigest()
    if not compare_digest(expected, sig):
        raise ValueError("Invalid OAuth state signature")
    payload = json.loads(raw.decode())
    if int(payload.get("exp") or 0) < int(time.time()):
        raise ValueError("OAuth state expired")
    return payload


def build_authorize_url(*, redirect_uri: str, state: str) -> str:
    if not google_configured():
        raise RuntimeError("Google OAuth is not configured")
    query = urlencode(
        {
            "client_id": google_client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code_for_id_token(*, code: str, redirect_uri: str) -> str:
    if not google_configured():
        raise RuntimeError("Google OAuth is not configured")
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": google_client_id(),
            "client_secret": google_client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise ValueError("Google token exchange failed")
    data = response.json()
    id_token_jwt = (data.get("id_token") or "").strip()
    if not id_token_jwt:
        raise ValueError("Google response missing id_token")
    return id_token_jwt


def verify_google_id_token(id_token_jwt: str) -> dict[str, str]:
    claims = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        google_client_id(),
    )
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid Google token issuer")
    sub = (claims.get("sub") or "").strip()
    email = (claims.get("email") or "").strip().lower()
    if not sub or not email:
        raise ValueError("Google token missing subject or email")
    if not claims.get("email_verified", True):
        raise ValueError("Google email is not verified")
    return {
        "google_sub": sub,
        "email": email,
        "display_name": (claims.get("name") or "").strip(),
    }


def profile_from_authorization_code(*, code: str, redirect_uri: str) -> dict[str, str]:
    token = exchange_code_for_id_token(code=code, redirect_uri=redirect_uri)
    return verify_google_id_token(token)
