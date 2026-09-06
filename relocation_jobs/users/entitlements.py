from __future__ import annotations

import os
from datetime import date, datetime, timezone

from relocation_jobs.broadcast.types import CapacityLimits
from relocation_jobs.users.repo import (
    claim_public_job_save,
    count_public_job_saves_on,
    get_user_by_id,
    is_user_admin,
    record_public_job_save,
    update_user_mcp_quota,
    update_user_plan,
)

PLANS = frozenset({"free", "full", "grandfathered"})

_DEFAULT_FREE_BOARD_CAP = 10
_DEFAULT_FREE_JOBS_PER_COMPANY = 3
_DEFAULT_FREE_TOTAL_POSITION_BUDGET = 30
_DEFAULT_FREE_MCP_DAILY = 20
_DEFAULT_FULL_MCP_DAILY = 500
_DEFAULT_FREE_PUBLIC_JOB_SAVES_PER_DAY = 3


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


def free_public_job_saves_per_day() -> int:
    raw = (
        os.environ.get("FREE_PUBLIC_JOB_SAVES_PER_DAY")
        or str(_DEFAULT_FREE_PUBLIC_JOB_SAVES_PER_DAY)
    ).strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_FREE_PUBLIC_JOB_SAVES_PER_DAY


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _public_job_save_fields(user: dict) -> dict:
    uid = int(user["id"])
    used = count_public_job_saves_on(uid, _utc_today())
    if plan_is_full_access(user.get("plan"), user_id=uid):
        return {"public_job_saves_used": used, "public_job_saves_remaining": None}
    remaining = max(0, free_public_job_saves_per_day() - used)
    return {"public_job_saves_used": used, "public_job_saves_remaining": remaining}


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
        **_public_job_save_fields(user),
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


def consume_public_job_save(user_id: int, job_id: int, slug: str) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    status = claim_public_job_save(
        user_id,
        job_id,
        slug,
        unlimited=plan_is_full_access(user.get("plan"), user_id=user_id),
        free_limit=free_public_job_saves_per_day(),
        saved_on=_utc_today(),
    )
    if status == "needs_credit":
        return {"ok": False, "needs_credit": True, "charged": False, "duplicate": False}
    return {
        "ok": True,
        "needs_credit": False,
        "charged": False,
        "duplicate": status == "duplicate",
    }


def record_credited_public_job_save(user_id: int, job_id: int, slug: str) -> None:
    record_public_job_save(user_id, job_id, slug, saved_on=_utc_today())
