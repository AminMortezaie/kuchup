from __future__ import annotations

from relocation_jobs.broadcast import repo as broadcast_repo
from relocation_jobs.broadcast.apply import apply_capacity_to_companies
from relocation_jobs.broadcast.types import (
    BoardCapacityMeta,
    CapacityLimits,
    PositionAssignment,
    RevealEvent,
)
from relocation_jobs.async_jobs.enqueue import enqueue_replace_assignment
from relocation_jobs.catalog.repo import get_company, list_jobs_for_company_keys
from relocation_jobs.core.job_identity import job_idempotency_key, normalize_job_url
from relocation_jobs.credits.service import (
    credit_balance,
    mark_usage_migration_done,
    refund_operation,
    spend_for_operation,
    usage_migration_done,
)
from relocation_jobs.credits.types import CreditOperation
from relocation_jobs.opportunities import repo as opportunities_repo
from relocation_jobs.users.entitlements import capacity_limits_for_user, plan_is_full_access
from relocation_jobs.users.repo import get_user_by_id, is_user_admin, load_job_tracking

_ENGAGED_TRACK_FLAGS = ("looking_to_apply", "applied", "pinned", "rejected")


def limits_for_user_id(user_id: int) -> CapacityLimits:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User not found: {user_id}")
    if is_user_admin(user_id):
        return CapacityLimits(None, None, None)
    return capacity_limits_for_user(user)


def capacity_meta_for_user(user_id: int) -> BoardCapacityMeta:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User not found: {user_id}")
    period = broadcast_repo.current_period_key()
    full_access = is_user_admin(user_id) or plan_is_full_access(
        user.get("plan"), user_id=user_id,
    )
    balance = credit_balance(user_id)
    if full_access:
        return BoardCapacityMeta(
            company_slots_used=opportunities_repo.count_user_opportunities(user_id),
            company_slots_cap=None,
            positions_used=broadcast_repo.consumed_count(user_id, period_key=period),
            positions_budget=None,
            jobs_per_company_peek=None,
            board_capped=False,
            positions_capped=False,
            upgrade_available=False,
            upgrade_reason=None,
            position_period=period,
            credits_promotional=balance.promotional,
            credits_purchased=balance.purchased,
            credits_total=balance.total,
            credits_next_reset_at=balance.next_reset_at,
        )
    limits = capacity_limits_for_user(user)
    used = broadcast_repo.consumed_count(user_id, period_key=period)
    slots_used = opportunities_repo.count_user_opportunities(user_id)
    board_capped = limits.company_slots is not None and slots_used >= limits.company_slots
    positions_capped = balance.total <= 0
    reason = None
    if positions_capped:
        reason = "position_budget"
    elif board_capped:
        reason = "company_slots"
    return BoardCapacityMeta(
        company_slots_used=slots_used,
        company_slots_cap=limits.company_slots,
        positions_used=used,
        positions_budget=limits.total_position_budget,
        jobs_per_company_peek=limits.jobs_per_company,
        board_capped=board_capped,
        positions_capped=positions_capped,
        upgrade_available=True,
        upgrade_reason=reason,
        position_period=period,
        credits_promotional=balance.promotional,
        credits_purchased=balance.purchased,
        credits_total=balance.total,
        credits_next_reset_at=balance.next_reset_at,
    )


def _raw_jobs(country: str, company_name: str) -> list[dict]:
    company = get_company(country, company_name) or {}
    return list(company.get("matching_jobs") or [])


def _current_catalog_assignment_keys(companies: list[dict]) -> set[tuple[str, str, str]]:
    company_keys = [
        (
            (company.get("country") or "").strip().lower(),
            (company.get("name") or "").strip(),
        )
        for company in companies
    ]
    jobs_by_company = list_jobs_for_company_keys(company_keys)
    return {
        (*company_key, (job.get("idempotency_key") or "").strip())
        for company_key, jobs in jobs_by_company.items()
        for job in jobs
        if (job.get("idempotency_key") or "").strip()
    }


def apply_capacity_to_board_page(user_id: int, companies: list[dict]) -> list[dict]:
    limits = limits_for_user_id(user_id)
    assignments = broadcast_repo.list_assignments(user_id)
    current_assignment_keys = set()
    if limits.jobs_per_company is not None:
        current_assignment_keys = _current_catalog_assignment_keys(companies)
    return apply_capacity_to_companies(
        companies,
        limits=limits,
        assignments=assignments,
        current_assignment_keys=current_assignment_keys,
        bypass=limits.unlimited,
    )


def _job_identity_key(job: dict) -> str:
    return (job.get("idempotency_key") or "").strip() or job_idempotency_key(
        job.get("url") or "",
    )


def _track_is_engaged(track: dict) -> bool:
    if track.get("not_for_me"):
        return False
    return any(track.get(flag) for flag in _ENGAGED_TRACK_FLAGS)


def _engaged_job_keys(
    user_id: int,
    country: str,
    company_name: str,
    jobs: list[dict],
) -> set[str]:
    tracking = load_job_tracking(user_id, country=country)
    by_url = {
        url: track
        for (track_country, track_company, url), track in tracking.items()
        if track_country == country and track_company == company_name
    }
    keys: set[str] = set()
    for job in jobs:
        track = by_url.get(normalize_job_url(job.get("url") or ""), {})
        if not _track_is_engaged(track):
            continue
        key = _job_identity_key(job)
        if key:
            keys.add(key)
    return keys


def visible_jobs_for_company(
    user_id: int,
    country: str,
    company_name: str,
    jobs: list[dict],
    *,
    extra_visible_keys: set[str] | frozenset[str] | None = None,
) -> tuple[list[dict], int]:
    if limits_for_user_id(user_id).unlimited:
        return list(jobs), 0
    extra = set(extra_visible_keys or ())
    extra |= _engaged_job_keys(user_id, country, company_name, jobs)
    capped = apply_capacity_to_board_page(
        user_id,
        [{"country": country, "name": company_name, "jobs": list(jobs)}],
    )[0]
    visible = list(capped.get("jobs") or [])
    seen = {_job_identity_key(job) for job in visible if _job_identity_key(job)}
    for job in jobs:
        key = _job_identity_key(job)
        if key and key in extra and key not in seen:
            visible.append(job)
            seen.add(key)
    hidden = max(
        0,
        len(jobs) - len([job for job in jobs if _job_identity_key(job) in seen]),
    )
    return visible, hidden


def filter_catalog_company_for_user(
    user_id: int,
    country: str,
    company: dict,
) -> dict:
    name = (company.get("name") or "").strip()
    jobs = list(company.get("matching_jobs") or [])
    visible, hidden = visible_jobs_for_company(user_id, country, name, jobs)
    if hidden == 0 and len(visible) == len(jobs):
        return company
    allowed = {_job_identity_key(job) for job in visible if _job_identity_key(job)}
    out = dict(company)
    out["matching_jobs"] = [
        job for job in jobs if _job_identity_key(job) in allowed
    ]
    out["jobs_hidden_count"] = hidden
    return out


def _role_delivery_key(
    period: str,
    country: str,
    company_name: str,
    job_key: str,
) -> str:
    return (
        f"role-delivery:{period}:{country.strip().lower()}:"
        f"{company_name.strip().lower()}:{job_key.strip()}"
    )


def import_month_usage(user_id: int, period: str | None = None) -> None:
    period = period or broadcast_repo.current_period_key()
    if usage_migration_done(user_id, period):
        return
    for assignment in broadcast_repo.list_assignments(user_id, period_key=period):
        if assignment.consumed_at is None:
            continue
        spend_for_operation(
            user_id,
            CreditOperation.ROLE_REPLACEMENT,
            idempotency_key=_role_delivery_key(
                period, assignment.country, assignment.company_name, assignment.job_key,
            ),
            metadata={"legacy_import": True, "source_job_key": assignment.job_key},
        )
    mark_usage_migration_done(user_id, period)


def _replacement_candidate(
    jobs: list[dict],
    assignments: list[PositionAssignment],
) -> dict | None:
    assigned_keys = {assignment.job_key for assignment in assignments}
    return next(
        (
            job
            for job in jobs
            if (job.get("idempotency_key") or "").strip()
            and (job.get("idempotency_key") or "").strip() not in assigned_keys
        ),
        None,
    )


def record_touch_and_maybe_reveal(user_id: int, event: RevealEvent) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User not found: {user_id}")
    if is_user_admin(user_id) or plan_is_full_access(user.get("plan"), user_id=user_id):
        return {"expanded": False, "reason": "unlimited"}
    period = broadcast_repo.current_period_key()
    key = event.job_key.strip() or job_idempotency_key(event.job_url)
    if not key:
        return {"expanded": False, "reason": "missing_job_key"}
    import_month_usage(user_id, period)
    newly_consumed = broadcast_repo.mark_assignment_consumed(
        user_id,
        country=event.country,
        company_name=event.company_name,
        job_key=key,
        job_url=event.job_url,
        job_title=event.job_title,
        action_kind=event.kind,
        period_key=period,
    )
    if not newly_consumed:
        return {
            "expanded": False,
            "consumed": False,
            "reason": "already_counted",
            "capacity": capacity_meta_for_user(user_id).as_dict(),
        }
    before = broadcast_repo.list_assignments(user_id, period_key=period)
    jobs = _raw_jobs(event.country, event.company_name)
    candidate = _replacement_candidate(jobs, before)
    if candidate is None:
        return {
            "expanded": False,
            "consumed": False,
            "reason": "no_replacement",
            "capacity": capacity_meta_for_user(user_id).as_dict(),
        }
    spend_key = _role_delivery_key(period, event.country, event.company_name, key)
    spent = spend_for_operation(
        user_id,
        CreditOperation.ROLE_REPLACEMENT,
        idempotency_key=spend_key,
        metadata={
            "country": event.country,
            "company_name": event.company_name,
            "source_job_key": key,
            "replacement_job_key": candidate["idempotency_key"],
        },
    )
    if not spent["spent"] or spent["deduplicated"]:
        return {
            "expanded": False,
            "consumed": False,
            "reason": "already_counted" if spent["deduplicated"] else "credits_exhausted",
            "capacity": capacity_meta_for_user(user_id).as_dict(),
        }
    try:
        queued = enqueue_replace_assignment(
            user_id,
            country=event.country,
            company_name=event.company_name,
            source_job_key=key,
        )
    except RuntimeError:
        refund_operation(user_id, spend_key=spend_key, reason="replacement_assignment_failed")
        return {
            "expanded": False,
            "consumed": False,
            "reason": "replacement_assignment_failed",
            "capacity": capacity_meta_for_user(user_id).as_dict(),
        }
    replacement_revealed = bool(queued.get("queued") or queued.get("synced"))
    if not replacement_revealed:
        refund_operation(user_id, spend_key=spend_key, reason="replacement_assignment_failed")
    return {
        "expanded": replacement_revealed,
        "consumed": replacement_revealed,
        "credits_spent": 1 if replacement_revealed else 0,
        "queued": bool(queued.get("queued")),
        "position_period": period,
        "capacity": capacity_meta_for_user(user_id).as_dict(),
    }
