from __future__ import annotations

import os


def vapid_public_key() -> str | None:
    raw = (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()
    return raw or None
