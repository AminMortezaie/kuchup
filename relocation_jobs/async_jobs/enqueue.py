from __future__ import annotations

from relocation_jobs.async_jobs.handlers import handle_reconcile_country, handle_reconcile_user
from relocation_jobs.async_jobs.types import (
    ReconcileCountryOpportunities,
    ReconcileUserOpportunities,
)
from relocation_jobs.core.sqs_client import (
    opportunity_refresh_queue_url,
    send_json_message,
    sqs_enabled,
)


def enqueue(message: ReconcileUserOpportunities | ReconcileCountryOpportunities) -> dict:
    payload = message.to_payload()
    if not sqs_enabled():
        if isinstance(message, ReconcileUserOpportunities):
            result = handle_reconcile_user(message)
        else:
            result = handle_reconcile_country(message)
        return {"queued": False, "synced": True, **result}
    message_id = send_json_message(opportunity_refresh_queue_url(), payload)
    return {"queued": True, "synced": False, "message_id": message_id, **payload}


def enqueue_user_opportunity_refresh(user_id: int) -> dict:
    return enqueue(ReconcileUserOpportunities(user_id=int(user_id)))


def enqueue_country_opportunity_refresh(country: str) -> dict:
    return enqueue(ReconcileCountryOpportunities(country=country))
