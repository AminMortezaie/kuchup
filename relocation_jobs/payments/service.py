from __future__ import annotations

from decimal import Decimal, InvalidOperation

from relocation_jobs.credits import repo as credits_repo
from relocation_jobs.credits.service import grant_order_credits, pack_for_checkout
from relocation_jobs.payments import nowpayments


FAILED_STATUSES = frozenset({"failed", "expired", "refunded"})


def _validate_paid_amount(order: dict, payload: dict) -> None:
    try:
        actual_minor = int(
            (Decimal(str(payload.get("price_amount"))) * Decimal("100")).quantize(
                Decimal("1"),
            )
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Payment amount is missing or invalid") from None
    currency = str(payload.get("price_currency") or "").strip().upper()
    if actual_minor != int(order["price_minor"]) or currency != order["currency"].upper():
        raise ValueError("Payment amount does not match the credit order")


def create_credit_checkout(user_id: int, pack_key: str, *, base_url: str) -> dict:
    pack = pack_for_checkout(pack_key)
    order_id = credits_repo.create_order(
        user_id,
        pack_key=pack.key,
        credits=pack.credits,
        price_minor=pack.price_minor,
        currency=pack.currency,
        provider=nowpayments.PROVIDER,
    )
    checkout = nowpayments.create_checkout(
        order_id=order_id,
        price_minor=pack.price_minor,
        currency=pack.currency,
        description=f"Kuchup {pack.label}",
        base_url=base_url,
    )
    credits_repo.update_order_checkout(
        order_id,
        provider_order_id=checkout.provider_order_id,
        checkout_url=checkout.checkout_url,
    )
    return {
        "order_id": order_id,
        "provider": nowpayments.PROVIDER,
        "checkout_url": checkout.checkout_url,
    }


def process_nowpayments_notification(payload: dict, signature: str) -> dict:
    notification = nowpayments.parse_notification(payload, signature)
    order = credits_repo.get_order_by_provider(
        nowpayments.PROVIDER, notification.provider_order_id,
    )
    if not order:
        raise LookupError("Payment order not found")
    if notification.status in nowpayments.PAID_STATUSES:
        _validate_paid_amount(order, notification.payload)
    result = {"ok": True, "paid": False, "status": notification.status}
    if notification.status in nowpayments.PAID_STATUSES:
        paid_order = credits_repo.mark_order_paid(
            nowpayments.PROVIDER, notification.provider_order_id,
        )
        granted = grant_order_credits(paid_order)
        result = {"ok": True, "paid": True, "granted": granted}
    elif notification.status in FAILED_STATUSES:
        failed_order = credits_repo.update_order_status(
            nowpayments.PROVIDER,
            notification.provider_order_id,
            notification.status,
        )
        if notification.status == "refunded":
            credits_repo.revoke_order_grant(
                failed_order,
                reason="provider_refund",
            )
    recorded = credits_repo.record_payment_event(
        provider=nowpayments.PROVIDER,
        event_id=notification.event_id,
        provider_order_id=notification.provider_order_id,
        payload=notification.payload,
    )
    return {**result, "deduplicated": not recorded}


def reconcile_order(order_id: int) -> dict:
    order = credits_repo.get_order(order_id)
    if not order:
        raise LookupError("Credit order not found")
    granted = False
    if order["status"] == "paid":
        granted = grant_order_credits(order)
    return {"order": order, "granted": granted}


def revoke_order_credits(order_id: int, *, reason: str) -> dict:
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("A reason is required")
    order = credits_repo.get_order(order_id)
    if not order:
        raise LookupError("Credit order not found")
    revoked = credits_repo.revoke_order_grant(order, reason=clean_reason)
    return {"order": order, "revoked_credits": revoked}
