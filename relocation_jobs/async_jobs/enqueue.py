from __future__ import annotations

import os
import subprocess

from relocation_jobs.async_jobs.types import (
    JobMessage,
    ReconcileCountryOpportunities,
    ReconcileUserOpportunities,
    ReplaceAssignment,
)
from relocation_jobs.core.sqs_client import (
    opportunity_refresh_queue_url,
    send_json_message,
    sqs_enabled,
)

_BIN_ENV = "ROLE_PROPAGATOR_BIN"


def _propagator_bin() -> str:
    return (os.environ.get(_BIN_ENV) or "").strip()


def _run_bin(args: list[str]) -> dict:
    completed = subprocess.run(
        [_propagator_bin(), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "role-propagator failed").strip()
        raise RuntimeError(detail)
    return {"queued": False, "synced": True}


def _bin_args(message: JobMessage) -> list[str]:
    if isinstance(message, ReconcileUserOpportunities):
        return ["--user", str(int(message.user_id))]
    if isinstance(message, ReconcileCountryOpportunities):
        return ["--country", (message.country or "").strip().lower()]
    return [
        "--replace",
        "--user",
        str(int(message.user_id)),
        "--country",
        (message.country or "").strip().lower(),
        "--company",
        (message.company_name or "").strip(),
        "--source-job-key",
        (message.source_job_key or "").strip(),
    ]


def enqueue(message: JobMessage) -> dict:
    payload = message.to_payload()
    if sqs_enabled():
        message_id = send_json_message(opportunity_refresh_queue_url(), payload)
        return {"queued": True, "synced": False, "message_id": message_id, **payload}
    if not _propagator_bin():
        raise RuntimeError(
            "assignment writer missing: set SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL or ROLE_PROPAGATOR_BIN"
        )
    ran = _run_bin(_bin_args(message))
    return {**ran, **payload}


def enqueue_user_opportunity_refresh(user_id: int) -> dict:
    return enqueue(ReconcileUserOpportunities(user_id=int(user_id)))


def enqueue_country_opportunity_refresh(country: str) -> dict:
    return enqueue(ReconcileCountryOpportunities(country=country))


def enqueue_replace_assignment(
    user_id: int,
    *,
    country: str,
    company_name: str,
    source_job_key: str = "",
) -> dict:
    return enqueue(
        ReplaceAssignment(
            user_id=int(user_id),
            country=country,
            company_name=company_name,
            source_job_key=source_job_key,
        )
    )
