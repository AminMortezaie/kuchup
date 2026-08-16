from __future__ import annotations

import logging

from relocation_jobs.async_jobs.handlers import handle_reconcile_country, handle_reconcile_user
from relocation_jobs.async_jobs.types import (
    ReconcileCountryOpportunities,
    ReconcileUserOpportunities,
    parse_message,
)
from relocation_jobs.core.sqs_client import (
    delete_message,
    opportunity_refresh_queue_url,
    receive_json_messages,
    sqs_enabled,
)
from relocation_jobs.opportunities import repo as opportunities_repo

LOGGER = logging.getLogger("relocation_jobs.async_jobs.dispatch")


def process_message(body: dict) -> dict:
    message = parse_message(body)
    if isinstance(message, ReconcileUserOpportunities):
        return handle_reconcile_user(message)
    if isinstance(message, ReconcileCountryOpportunities):
        return handle_reconcile_country(message)
    raise ValueError(f"Unhandled message: {type(message)!r}")


def poll_once(
    *,
    max_messages: int = 5,
    wait_seconds: int = 10,
) -> dict:
    if not sqs_enabled():
        return {"skipped": True, "reason": "sqs_disabled"}
    queue_url = opportunity_refresh_queue_url()
    messages = receive_json_messages(
        queue_url,
        max_messages=max_messages,
        wait_seconds=wait_seconds,
    )
    processed = 0
    errors = 0
    for message in messages:
        try:
            process_message(message["body"])
            delete_message(queue_url, message["receipt_handle"])
            processed += 1
        except Exception:
            errors += 1
            LOGGER.exception("async job failed: %s", message.get("message_id"))
    return {
        "received": len(messages),
        "processed": processed,
        "errors": errors,
        "preference_users": len(opportunities_repo.list_all_user_ids()),
    }
