from __future__ import annotations

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_CONFIRM_SALT = "panel-email-confirm"
_CONFIRM_MAX_AGE_SECONDS = 48 * 3600


def _confirm_secret() -> str:
    return os.environ.get("PANEL_SECRET_KEY", "").strip() or "dev-panel-email-confirm"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_confirm_secret(), salt=_CONFIRM_SALT)


def encode_email_confirm_token(user_id: int) -> str:
    return _serializer().dumps({"uid": int(user_id)})


def decode_email_confirm_token(token: str) -> int:
    raw = (token or "").strip()
    if not raw:
        raise ValueError("Invalid confirmation link")
    try:
        payload = _serializer().loads(raw, max_age=_CONFIRM_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise ValueError("Confirmation link expired") from exc
    except BadSignature as exc:
        raise ValueError("Invalid confirmation link") from exc
    user_id = int(payload.get("uid") or 0)
    if user_id <= 0:
        raise ValueError("Invalid confirmation link")
    return user_id
