from __future__ import annotations

from relocation_jobs.opportunities.types import (
    CompanyCandidate,
    MatchInput,
    OpportunityRow,
    UserPreferences,
)

_SENIORITY_TOKENS = {
    "junior": ("junior", "jr", "entry"),
    "mid": ("mid", "middle", "intermediate"),
    "senior": ("senior", "sr"),
    "staff": ("staff", "principal", "lead"),
}


def _normalize_tokens(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        token = (value or "").strip().lower()
        if token and token not in out:
            out.append(token)
    return tuple(out)


def _matches_keywords(candidate: CompanyCandidate, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    haystack = f"{candidate.company_name} {candidate.titles_blob}".lower()
    return any(keyword in haystack for keyword in keywords)


def _matches_seniority(candidate: CompanyCandidate, seniority: str) -> bool:
    key = (seniority or "").strip().lower()
    if not key:
        return True
    tokens = _SENIORITY_TOKENS.get(key, (key,))
    haystack = f"{candidate.company_name} {candidate.titles_blob}".lower()
    return any(token in haystack for token in tokens)


def match_opportunities(payload: MatchInput) -> list[OpportunityRow]:
    prefs = payload.preferences
    countries = _normalize_tokens(prefs.target_countries)
    if not countries:
        return []
    keywords = _normalize_tokens(prefs.keywords)
    selected = [
        candidate
        for candidate in payload.candidates
        if candidate.country in countries
        and _matches_keywords(candidate, keywords)
        and _matches_seniority(candidate, prefs.seniority)
        and (not payload.require_open_roles or candidate.open_job_count > 0)
    ]
    selected.sort(
        key=lambda row: (row.newest_fetched or "", row.company_name.lower()),
        reverse=True,
    )
    if payload.board_company_cap is not None and not payload.is_admin:
        selected = selected[: payload.board_company_cap]
    return [
        OpportunityRow(
            country=row.country,
            company_name=row.company_name,
            newest_fetched=row.newest_fetched or "",
        )
        for row in selected
    ]


def empty_preferences(user_id: int) -> UserPreferences:
    return UserPreferences(user_id=user_id)
