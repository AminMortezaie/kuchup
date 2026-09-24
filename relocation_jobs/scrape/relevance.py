from __future__ import annotations

import re
from collections.abc import Callable

from relocation_jobs.shared.predicates import any_of

_ENGINEER_TITLE_EXCLUDE_SKIP = frozenset({"marketing", "hr"})

_IRRELEVANT_TITLE_RULES: tuple[Callable[[tuple[str, list[str]]], bool], ...] = (
    lambda ctx: bool(re.search(r"\bchief technology officer\b|\bcto\b", ctx[0])),
    lambda ctx: any(kw in ctx[0] for kw in ctx[1]),
    lambda ctx: bool(re.search(r"\bstaff\b", ctx[0])) and not re.search(
        r"senior\s*/\s*staff", ctx[0],
    ),
    lambda ctx: "cloud engineer" in ctx[0] and "backend" not in ctx[0] and "software" not in ctx[0],
    lambda ctx: "ai platform" in ctx[0] and "backend" not in ctx[0] and "software" not in ctx[0],
)


def _title_excludes(title_lower: str, exclude: list[str]) -> list[str]:
    if re.search(r"\b(engineer|developer|programmer)\b", title_lower):
        return [
            kw for kw in exclude
            if kw.strip() not in _ENGINEER_TITLE_EXCLUDE_SKIP
        ]
    return exclude


def is_relevant(title: str, *, include: list[str], exclude: list[str]) -> bool:
    t = title.lower()
    if not any(kw in t for kw in include):
        return False
    ctx = (t, _title_excludes(t, exclude))
    return not any_of(ctx, _IRRELEVANT_TITLE_RULES)


def hidden_by_active_excludes(title: str, exclude: list[str]) -> bool:
    t = (title or "").lower()
    ctx = (t, _title_excludes(t, exclude))
    return any_of(ctx, _IRRELEVANT_TITLE_RULES)


def explain_title_filter(title: str, *, include: list[str], exclude: list[str]) -> str:
    t = (title or "").lower()
    if re.search(r"\bchief technology officer\b|\bcto\b", t):
        return "Title excluded (CTO)"
    if not any(kw in t for kw in include):
        return "Title not relevant (no backend/software keyword)"
    excludes = _title_excludes(t, exclude)
    for kw in excludes:
        if kw in t:
            return f"Title excluded ({kw.strip() or kw})"
    if re.search(r"\bstaff\b", t) and not re.search(r"senior\s*/\s*staff", t):
        return "Title excluded (staff level)"
    if "cloud engineer" in t and "backend" not in t and "software" not in t:
        return "Title excluded (cloud engineer without backend/software)"
    if "ai platform" in t and "backend" not in t and "software" not in t:
        return "Title excluded (AI platform without backend/software)"
    return "Title not relevant"
