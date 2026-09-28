from __future__ import annotations

import logging
import subprocess

from relocation_jobs.core.sqs_client import job_notify_queue_url, send_json_message, sqs_enabled_for

LOGGER = logging.getLogger(__name__)

_NOTIFY_ENV = "SQS_JOB_NOTIFY_QUEUE_URL"
_WORKER_BIN_ENV = "NOTIFICATION_WORKER_BIN"


def enqueue_country_notify_wave(*, country: str, fetch_run_id: int) -> dict:
    run_id = int(fetch_run_id or 0)
    country_key = (country or "").strip().lower()
    if run_id <= 0 or not country_key:
        return {"queued": False, "reason": "missing_wave"}
    payload = {
        "type": "country_wave",
        "country": country_key,
        "fetch_run_id": run_id,
    }
    queue_url = job_notify_queue_url()
    if sqs_enabled_for(_NOTIFY_ENV):
        try:
            message_id = send_json_message(queue_url, payload)
            return {"queued": True, "message_id": message_id, **payload}
        except Exception as exc:
            LOGGER.warning(
                "notify enqueue failed country=%s fetch_run_id=%s: %s",
                country_key,
                run_id,
                exc,
            )
            return {"queued": False, "error": str(exc), **payload}
    import os

    bin_path = (os.environ.get(_WORKER_BIN_ENV) or "").strip()
    if not bin_path:
        return {"queued": False, "reason": "notify_queue_unconfigured", **payload}
    try:
        completed = subprocess.run(
            [bin_path, "--country", country_key, "--fetch-run-id", str(run_id)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "notification worker failed").strip()
            LOGGER.warning("notify worker bin failed: %s", detail)
            return {"queued": False, "synced": False, "error": detail, **payload}
    except OSError as exc:
        LOGGER.warning("notify worker bin missing: %s", exc)
        return {"queued": False, "error": str(exc), **payload}
    return {"queued": False, "synced": True, **payload}
