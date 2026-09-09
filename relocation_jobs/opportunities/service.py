from __future__ import annotations

from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.opportunities.types import (
    DEFAULT_TARGET_COUNTRIES,
    BoardOpportunityScope,
    UserPreferences,
)
from relocation_jobs.users.entitlements import board_company_cap_for_user, normalize_plan
from relocation_jobs.users.repo import get_user_by_id, is_user_admin


def opportunity_company_key(country: str, company_name: str) -> tuple[str, str]:
    return ((country or "").strip().lower(), (company_name or "").strip().lower())


def ensure_default_preferences(user_id: int) -> UserPreferences:
    prefs = opportunities_repo.get_user_preferences(user_id)
    if prefs.target_countries:
        return prefs
    return opportunities_repo.save_user_preferences(
        user_id,
        target_countries=list(DEFAULT_TARGET_COUNTRIES),
        preferences_confirmed=False,
    )


def visible_preferences(user_id: int) -> UserPreferences:
    prefs = opportunities_repo.get_user_preferences(user_id)
    if prefs.target_countries:
        return prefs
    return UserPreferences(
        user_id=user_id,
        target_countries=DEFAULT_TARGET_COUNTRIES,
        preferences_confirmed=False,
    )


def resolve_board_opportunity_scope(user_id: int) -> BoardOpportunityScope:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User not found: {user_id}")
    plan = normalize_plan(user.get("plan"))
    prefs = visible_preferences(user_id)
    cap = board_company_cap_for_user(user)
    needs_preferences = not prefs.preferences_confirmed
    if is_user_admin(user_id):
        return BoardOpportunityScope(
            bypass=True,
            company_keys=frozenset(),
            country_keys=frozenset(),
            opportunity_count=0,
            needs_preferences=False,
            board_capped=False,
            board_company_cap=None,
            plan=plan,
            target_countries=prefs.target_countries,
        )
    rows = opportunities_repo.list_user_opportunity_companies(user_id)
    company_keys = frozenset(
        opportunity_company_key(row.get("country") or "", row.get("company_name") or "")
        for row in rows
    )
    country_keys = frozenset(prefs.target_countries) or frozenset(
        country for country, _ in company_keys
    )
    opportunity_count = len(company_keys)
    return BoardOpportunityScope(
        bypass=False,
        company_keys=company_keys,
        country_keys=country_keys,
        opportunity_count=opportunity_count,
        needs_preferences=needs_preferences,
        board_capped=cap is not None and opportunity_count >= cap,
        board_company_cap=cap,
        plan=plan,
        target_countries=prefs.target_countries,
    )


def board_scope_meta(scope: BoardOpportunityScope) -> dict:
    return {
        "plan": scope.plan,
        "opportunity_count": None if scope.bypass else scope.opportunity_count,
        "needs_preferences": scope.needs_preferences,
        "board_capped": scope.board_capped,
        "board_company_cap": scope.board_company_cap,
        "upgrade_available": (not scope.bypass) and scope.plan == "free",
        "target_countries": list(scope.target_countries),
    }


def save_preferences_and_refresh(
    user_id: int,
    *,
    target_countries: list[str] | tuple[str, ...],
    seniority: str = "",
    keywords: list[str] | tuple[str, ...] = (),
    remote_ok: bool = False,
) -> dict:
    prefs = opportunities_repo.save_user_preferences(
        user_id,
        target_countries=target_countries,
        seniority=seniority,
        keywords=keywords,
        remote_ok=remote_ok,
        preferences_confirmed=True,
    )
    refresh = enqueue_user_opportunity_refresh(user_id)
    return {
        "preferences": {
            "target_countries": list(prefs.target_countries),
            "seniority": prefs.seniority,
            "keywords": list(prefs.keywords),
            "remote_ok": prefs.remote_ok,
            "preferences_confirmed": prefs.preferences_confirmed,
        },
        "refresh": refresh,
    }
