from __future__ import annotations

import json
import os
import threading
from typing import Any

_OPPORTUNITY_REFRESH_ENV = "SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL"

_lock = threading.Lock()
_client = None


def queue_url_from_env(env_key: str) -> str:
    return (os.environ.get(env_key) or "").strip()


def opportunity_refresh_queue_url() -> str:
    return queue_url_from_env(_OPPORTUNITY_REFRESH_ENV)


def sqs_enabled_for(env_key: str) -> bool:
    return bool(queue_url_from_env(env_key))


def sqs_enabled() -> bool:
    return sqs_enabled_for(_OPPORTUNITY_REFRESH_ENV)


def get_sqs():
    global _client
    with _lock:
        if _client is None:
            import boto3

            _client = boto3.client(
                "sqs",
                region_name=(os.environ.get("AWS_REGION") or "eu-central-1").strip()
                or "eu-central-1",
            )
        return _client


def reset_sqs_client() -> None:
    global _client
    with _lock:
        _client = None


def send_json_message(queue_url: str, payload: dict[str, Any]) -> str:
    if not queue_url:
        raise RuntimeError("SQS queue URL is empty")
    response = get_sqs().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload, separators=(",", ":"), sort_keys=True),
    )
    return str(response.get("MessageId") or "")


def receive_json_messages(
    queue_url: str,
    *,
    max_messages: int = 5,
    wait_seconds: int = 10,
    visibility_timeout: int = 60,
) -> list[dict[str, Any]]:
    if not queue_url:
        raise RuntimeError("SQS queue URL is empty")
    response = get_sqs().receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max(1, min(max_messages, 10)),
        WaitTimeSeconds=max(0, min(wait_seconds, 20)),
        VisibilityTimeout=max(1, visibility_timeout),
        AttributeNames=["ApproximateReceiveCount"],
    )
    out: list[dict[str, Any]] = []
    for raw in response.get("Messages") or []:
        body = json.loads(raw.get("Body") or "{}")
        out.append(
            {
                "receipt_handle": raw.get("ReceiptHandle") or "",
                "message_id": raw.get("MessageId") or "",
                "body": body,
                "receive_count": int(
                    ((raw.get("Attributes") or {}).get("ApproximateReceiveCount")) or 1
                ),
            }
        )
    return out


def delete_message(queue_url: str, receipt_handle: str) -> None:
    if not queue_url or not receipt_handle:
        return
    get_sqs().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
