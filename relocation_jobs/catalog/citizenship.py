from __future__ import annotations

US_CITIZENSHIP = "US"
_ALLOWED = frozenset({"", US_CITIZENSHIP})


def normalize_citizenship_required(raw: str | None) -> str:
    code = str(raw or "").strip().upper()
    if code not in _ALLOWED:
        raise ValueError("citizenship_required must be US or empty")
    return code


def citizenship_code_for_write(company: dict | None) -> str:
    raw = (company or {}).get("citizenship_required")
    code = str(raw or "").strip().upper()
    return code if code == US_CITIZENSHIP else ""


def displayed_citizenship(company: dict | None) -> str:
    code = ((company or {}).get("citizenship_required") or "").strip().upper()
    return code if code == US_CITIZENSHIP else ""
