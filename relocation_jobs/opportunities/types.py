from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TARGET_COUNTRIES: tuple[str, ...] = ("germany",)


@dataclass(frozen=True)
class UserPreferences:
    user_id: int
    target_countries: tuple[str, ...] = ()
    seniority: str = ""
    keywords: tuple[str, ...] = ()
    remote_ok: bool = False
    preferences_confirmed: bool = False
    opportunities_refreshed_at: str | None = None


@dataclass(frozen=True)
class CompanyCandidate:
    country: str
    company_name: str
    newest_fetched: str = ""
    titles_blob: str = ""
    open_job_count: int = 0


@dataclass(frozen=True)
class OpportunityRow:
    country: str
    company_name: str
    newest_fetched: str = ""
    revealed_job_count: int = 0
    engaged: bool = False


@dataclass(frozen=True)
class MatchInput:
    plan: str
    is_admin: bool
    preferences: UserPreferences
    board_company_cap: int | None
    candidates: tuple[CompanyCandidate, ...] = field(default_factory=tuple)
    require_open_roles: bool = True


@dataclass(frozen=True)
class BoardOpportunityScope:
    bypass: bool
    company_keys: frozenset[tuple[str, str]]
    country_keys: frozenset[str]
    opportunity_count: int
    needs_preferences: bool
    board_capped: bool
    board_company_cap: int | None
    plan: str
    target_countries: tuple[str, ...]
