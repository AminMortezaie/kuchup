from __future__ import annotations

import os
from datetime import date

from relocation_jobs.broadcast.types import CapacityLimits
from relocation_jobs.users.repo import get_user_by_id, is_user_admin, update_user_mcp_quota, update_user_plan

PLANS = frozenset({"free", "full", "grandfathered"})

_DEFAULT_FREE_BOARD_CAP = 10
_DEFAULT_FREE_JOBS_PER_COMPANY = 3
_DEFAULT_FREE_TOTAL_POSITION_BUDGET = 30
_DEFAULT_FREE_MCP_DAILY = 20
_DEFAULT_FULL_MCP_DAILY = 500


def free_board_company_cap() -> int:
    raw = (os.environ.get("FREE_BOARD_COMPANY_CAP") or str(_DEFAULT_FREE_BOARD_CAP)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_FREE_BOARD_CAP


def free_jobs_per_company() -> int:
    raw = (os.environ.get("FREE_JOBS_PER_COMPANY") or str(_DEFAULT_FREE_JOBS_PER_COMPANY)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_FREE_JOBS_PER_COMPANY


def free_total_position_budget() -> int:
    raw = (
        os.environ.get("FREE_TOTAL_POSITION_BUDGET") or str(_DEFAULT_FREE_TOTAL_POSITION_BUDGET)
    ).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_FREE_TOTAL_POSITION_BUDGET


def free_mcp_daily_requests() -> int:
    raw = (os.environ.get("FREE_MCP_DAILY_REQUESTS") or str(_DEFAULT_FREE_MCP_DAILY)).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_FREE_MCP_DAILY


def full_mcp_daily_requests() -> int:
    raw = (os.environ.get("FULL_MCP_DAILY_REQUESTS") or str(_DEFAULT_FULL_MCP_DAILY)).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_FULL_MCP_DAILY


def normalize_plan(plan: str | None) -> str:
    value = (plan or "free").strip().lower() or "free"
    if value not in PLANS:
        raise ValueError(f"Unknown plan: {plan}")
    return value


def plan_is_full_access(plan: str | None, *, user_id: int | None = None) -> bool:
    if user_id is not None and is_user_admin(user_id):
        return True
    return normalize_plan(plan) in ("full", "grandfathered")


def board_company_cap_for_user(user: dict) -> int | None:
    if plan_is_full_access(user.get("plan"), user_id=int(user["id"])):
        return None
    return free_board_company_cap()


def capacity_limits_for_user(user: dict) -> CapacityLimits:
    if plan_is_full_access(user.get("plan"), user_id=int(user["id"])):
        return CapacityLimits(None, None, None)
    return CapacityLimits(
        company_slots=free_board_company_cap(),
        jobs_per_company=free_jobs_per_company(),
        total_position_budget=free_total_position_budget(),
    )


def mcp_daily_limit_for_user(user: dict) -> int | None:
    if is_user_admin(int(user["id"])):
        return None
    if plan_is_full_access(user.get("plan")):
        limit = full_mcp_daily_requests()
        return None if limit == 0 else limit
    return free_mcp_daily_requests()


def entitlement_status(user_id: int) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    plan = normalize_plan(user.get("plan"))
    limit = mcp_daily_limit_for_user(user)
    today = date.today().isoformat()
    used = int(user.get("mcp_quota_used") or 0)
    if (user.get("mcp_quota_date") or "") != today:
        used = 0
    remaining = None if limit is None else max(0, limit - used)
    caps = capacity_limits_for_user(user)
    return {
        "plan": plan,
        "board_company_cap": board_company_cap_for_user(user),
        "jobs_per_company": caps.jobs_per_company,
        "total_position_budget": caps.total_position_budget,
        "mcp_daily_limit": limit,
        "mcp_daily_used": used,
        "mcp_daily_remaining": remaining,
        "is_admin": is_user_admin(user_id),
    }


def set_plan(user_id: int, plan: str) -> dict:
    normalized = normalize_plan(plan)
    if not update_user_plan(user_id, normalized):
        raise LookupError("User not found")
    return entitlement_status(user_id)


def consume_mcp_quota(user_id: int) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    limit = mcp_daily_limit_for_user(user)
    today = date.today().isoformat()
    used = int(user.get("mcp_quota_used") or 0)
    if (user.get("mcp_quota_date") or "") != today:
        used = 0
    if limit is not None and used >= limit:
        raise PermissionError(
            f"MCP daily quota exceeded ({limit}/day on plan {normalize_plan(user.get('plan'))}). "
            "Upgrade for higher limits."
        )
    used += 1
    update_user_mcp_quota(user_id, quota_date=today, quota_used=used)
    return entitlement_status(user_id)
