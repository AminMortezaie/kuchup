from __future__ import annotations

import logging

from relocation_jobs.core.job_identity import job_idempotency_key
from relocation_jobs.notifications import repo as notifications_repo
from relocation_jobs.notifications import send as push_send
from relocation_jobs.users.entitlements import normalize_plan
from relocation_jobs.users.repo import get_user_by_id

LOGGER = logging.getLogger(__name__)

_PUSH_TITLE = "Kuchup"


def new_jobs_notification_body(count: int) -> str:
    n = int(count)
    if n == 1:
        return "1 new job found!"
    return f"{n} new jobs found!"


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


def send_after_country_wave(*, country: str, fetch_run_id: int) -> dict:
    run_id = int(fetch_run_id)
    if run_id <= 0:
        return {"skipped": True, "reason": "missing_fetch_run_id"}
    if not push_send.vapid_configured():
        return {"skipped": True, "reason": "vapid_not_configured"}
    country_key = (country or "").strip().lower()
    notified = 0
    skipped_zero = 0
    skipped_claim = 0
    for user_id in notifications_repo.list_full_plan_subscribed_user_ids():
        count = notifications_repo.count_wave_jobs_for_user(user_id, run_id)
        if count <= 0:
            skipped_zero += 1
            continue
        if notifications_repo.push_wave_already_sent(user_id, run_id):
            skipped_claim += 1
            continue
        body = new_jobs_notification_body(count)
        result = push_send.send_user_notification(
            user_id,
            title=_PUSH_TITLE,
            body=body,
        )
        if result["sent"] > 0:
            notifications_repo.claim_push_sent(user_id, run_id)
            notified += 1
        LOGGER.info(
            "web_push_wave country=%s fetch_run_id=%s user_id=%s count=%s sent=%s",
            country_key,
            run_id,
            user_id,
            count,
            result["sent"],
        )
    return {
        "country": country_key,
        "fetch_run_id": run_id,
        "notified_users": notified,
        "skipped_zero": skipped_zero,
        "skipped_claim": skipped_claim,
    }


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
