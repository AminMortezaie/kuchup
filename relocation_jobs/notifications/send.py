from __future__ import annotations

import json
import logging
import os

from pywebpush import WebPushException, webpush

from relocation_jobs.notifications import repo as notifications_repo

LOGGER = logging.getLogger(__name__)


def vapid_public_key() -> str | None:
    raw = (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()
    return raw or None


def vapid_configured() -> bool:
    return bool(vapid_public_key() and (os.environ.get("VAPID_PRIVATE_KEY") or "").strip())


def _vapid_claims() -> dict:
    subject = (os.environ.get("VAPID_SUBJECT") or "mailto:hello@kuchup.com").strip()
    return {"sub": subject}


def send_to_subscription(subscription: dict, *, title: str, body: str) -> None:
    if not vapid_configured():
        raise RuntimeError("Web Push is not configured (VAPID keys missing)")
    payload = json.dumps({"title": title, "body": body})
    webpush(
        subscription_info={
            "endpoint": subscription["endpoint"],
            "keys": {
                "p256dh": subscription["p256dh"],
                "auth": subscription["auth"],
            },
        },
        data=payload,
        vapid_private_key=(os.environ.get("VAPID_PRIVATE_KEY") or "").strip(),
        vapid_claims=_vapid_claims(),
    )


def send_user_notification(user_id: int, *, title: str, body: str) -> dict:
    subs = notifications_repo.list_subscriptions_for_user(user_id)
    sent = 0
    gone = 0
    errors = 0
    for row in subs:
        try:
            send_to_subscription(row, title=title, body=body)
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 410:
                notifications_repo.delete_subscription_by_endpoint(row["endpoint"])
                gone += 1
            else:
                errors += 1
                LOGGER.warning(
                    "web push failed user_id=%s endpoint=%s status=%s",
                    user_id,
                    row.get("endpoint"),
                    status,
                )
        except Exception as exc:
            errors += 1
            LOGGER.warning(
                "web push failed user_id=%s: %s",
                user_id,
                exc,
            )
    return {"sent": sent, "gone": gone, "errors": errors}
