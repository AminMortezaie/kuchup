from __future__ import annotations

import os


def vapid_public_key() -> str | None:
    raw = (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()
    return raw or None


def vapid_configured() -> bool:
    return bool(vapid_public_key() and (os.environ.get("VAPID_PRIVATE_KEY") or "").strip())
