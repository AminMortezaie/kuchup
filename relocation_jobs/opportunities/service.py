from __future__ import annotations

from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.opportunities.types import BoardOpportunityScope
from relocation_jobs.users.entitlements import board_company_cap_for_user, normalize_plan
from relocation_jobs.users.repo import get_user_by_id, is_user_admin


def opportunity_company_key(country: str, company_name: str) -> tuple[str, str]:
    return ((country or "").strip().lower(), (company_name or "").strip().lower())


def ensure_user_preferences_row(user_id: int) -> None:
    opportunities_repo.ensure_user_preferences_row(user_id)


def resolve_board_opportunity_scope(user_id: int) -> BoardOpportunityScope:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User not found: {user_id}")
    plan = normalize_plan(user.get("plan"))
    cap = board_company_cap_for_user(user)
    if is_user_admin(user_id):
        return BoardOpportunityScope(
            bypass=True,
            company_keys=frozenset(),
            opportunity_count=0,
            board_capped=False,
            board_company_cap=None,
            plan=plan,
        )
    rows = opportunities_repo.list_user_opportunity_companies(user_id)
    company_keys = frozenset(
        opportunity_company_key(row.get("country") or "", row.get("company_name") or "")
        for row in rows
    )
    opportunity_count = len(company_keys)
    return BoardOpportunityScope(
        bypass=False,
        company_keys=company_keys,
        opportunity_count=opportunity_count,
        board_capped=cap is not None and opportunity_count >= cap,
        board_company_cap=cap,
        plan=plan,
    )


def board_scope_meta(scope: BoardOpportunityScope) -> dict:
    return {
        "plan": scope.plan,
        "opportunity_count": None if scope.bypass else scope.opportunity_count,
        "board_capped": scope.board_capped,
        "board_company_cap": scope.board_company_cap,
        "upgrade_available": (not scope.bypass) and scope.plan == "free",
    }
