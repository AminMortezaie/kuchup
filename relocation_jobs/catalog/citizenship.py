from __future__ import annotations

from urllib.parse import urlparse

US_CITIZENSHIP = "US"
_ALLOWED = frozenset({"", US_CITIZENSHIP})


def _hostname(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "//" + raw
    host = (urlparse(raw).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def url_requires_us_citizenship(url: str) -> bool:
    host = _hostname(url)
    if not host.endswith(".myworkdayjobs.com"):
        return False
    return host.split(".", 1)[0] == "gdit"


def normalize_citizenship_required(raw: str | None) -> str:
    code = str(raw or "").strip().upper()
    if code not in _ALLOWED:
        raise ValueError("citizenship_required must be US or empty")
    return code


def citizenship_code_for_write(company: dict | None) -> str:
    company = company or {}
    stored = (company.get("citizenship_required") or "").strip().upper()
    if stored:
        return stored
    careers = company.get("careers_url") or ""
    ats = company.get("ats_url") or ""
    if url_requires_us_citizenship(careers) or url_requires_us_citizenship(ats):
        return US_CITIZENSHIP
    return ""


def displayed_citizenship(company: dict | None) -> str:
    code = ((company or {}).get("citizenship_required") or "").strip().upper()
    return code if code == US_CITIZENSHIP else ""
