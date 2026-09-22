from __future__ import annotations

import os

from relocation_jobs.core.ats_constants import PLAYWRIGHT_REQUIRED_ATS
from relocation_jobs.core.ats_detection import PLAYWRIGHT_AVAILABLE

_KIND_HTTP = "http"
_KIND_PLAYWRIGHT = "playwright"
_KIND_ALL = "all"
_VALID_KINDS = frozenset({_KIND_HTTP, _KIND_PLAYWRIGHT, _KIND_ALL})


def worker_kind() -> str:
    raw = (os.environ.get("FETCH_WORKER_KIND") or "").strip().lower()
    if raw:
        if raw not in _VALID_KINDS:
            raise ValueError(f"Unknown FETCH_WORKER_KIND: {raw}")
        return raw
    return _KIND_ALL if PLAYWRIGHT_AVAILABLE else _KIND_HTTP


def worker_includes_ats(ats_type: str | None) -> bool:
    key = (ats_type or "").strip().lower()
    required = key in PLAYWRIGHT_REQUIRED_ATS
    if required and not PLAYWRIGHT_AVAILABLE:
        return False
    kind = worker_kind()
    if kind == _KIND_HTTP:
        return not required
    if kind == _KIND_PLAYWRIGHT:
        return required
    return True
