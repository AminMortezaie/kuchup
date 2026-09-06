"""String helpers for company names."""

from __future__ import annotations

import re


def slug_from_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def public_job_slug_base(company_name: str, title: str) -> str:
    company = slug_from_name(company_name) or "company"
    role = slug_from_name(title) or "role"
    return f"{company}-{role}"
