from __future__ import annotations

from dataclasses import dataclass


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
class BoardOpportunityScope:
    bypass: bool
    company_keys: frozenset[tuple[str, str]]
    opportunity_count: int
    board_capped: bool
    board_company_cap: int | None
    plan: str
