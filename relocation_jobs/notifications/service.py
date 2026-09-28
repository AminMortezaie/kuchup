from __future__ import annotations

from relocation_jobs.core.job_identity import job_idempotency_key
from relocation_jobs.notifications import repo as notifications_repo
from relocation_jobs.users.entitlements import normalize_plan
from relocation_jobs.users.repo import get_user_by_id


def plan_eligible_for_push(plan: str | None) -> bool:
    return normalize_plan(plan) in ("full", "grandfathered")


def user_eligible_for_push(user_id: int) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    return plan_eligible_for_push(user.get("plan"))


def job_keys_from_slim_jobs(jobs: list[dict]) -> list[str]:
    keys: list[str] = []
    for job in jobs or []:
        key = (job.get("idempotency_key") or "").strip()
        if not key:
            key = job_idempotency_key((job.get("url") or "").strip())
        if key:
            keys.append(key)
    return keys


def record_fetch_wave_jobs(
    fetch_run_id: int,
    country: str,
    company_name: str,
    slim_jobs: list[dict],
) -> None:
    notifications_repo.record_wave_jobs(
        fetch_run_id,
        country,
        company_name,
        job_keys_from_slim_jobs(slim_jobs),
    )


def save_subscription(user_id: int, payload: dict) -> None:
    if not user_eligible_for_push(user_id):
        raise PermissionError("Web Push is available on Full Access only")
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    notifications_repo.upsert_subscription(
        user_id,
        endpoint=endpoint,
        p256dh=(keys.get("p256dh") or "").strip(),
        auth=(keys.get("auth") or "").strip(),
    )


def remove_subscription(user_id: int, payload: dict) -> bool:
    endpoint = (payload.get("endpoint") or "").strip()
    return notifications_repo.delete_subscription(user_id, endpoint=endpoint)
