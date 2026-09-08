from __future__ import annotations

from decimal import Decimal, InvalidOperation

from relocation_jobs.credits import repo as credits_repo
from relocation_jobs.credits.service import grant_order_credits
from relocation_jobs.opportunities.service import refresh_user_opportunities
from relocation_jobs.payments import nowpayments
from relocation_jobs.payments.catalog import sku_for_checkout
from relocation_jobs.payments.types import ORDER_KIND_FULL_ACCESS
from relocation_jobs.users.entitlements import (
    normalize_plan,
    plan_is_full_access,
    set_plan,
)
from relocation_jobs.users.repo import get_user_by_id, is_user_admin


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


def _return_query(kind: str) -> str:
    return "upgrade" if kind == ORDER_KIND_FULL_ACCESS else "credits"


def create_checkout_for_sku(user_id: int, sku_key: str, *, base_url: str) -> dict:
    sku = sku_for_checkout(sku_key)
    origin = nowpayments.public_base_url(base_url)
    order_id = credits_repo.create_order(
        user_id,
        pack_key=sku.key,
        credits=sku.credits,
        price_minor=sku.price_minor,
        currency=sku.currency,
        provider=nowpayments.PROVIDER,
        kind=sku.kind,
    )
    checkout = nowpayments.create_checkout(
        order_id=order_id,
        price_minor=sku.price_minor,
        currency=sku.currency,
        description=f"Kuchup {sku.label}",
        base_url=origin,
        return_query=_return_query(sku.kind),
    )
    credits_repo.update_order_checkout(
        order_id,
        provider_order_id=checkout.provider_order_id,
        checkout_url=checkout.checkout_url,
    )
    return {
        "order_id": order_id,
        "provider": nowpayments.PROVIDER,
        "sku": sku.key,
        "kind": sku.kind,
        "checkout_url": checkout.checkout_url,
    }


def create_credit_checkout(user_id: int, pack_key: str, *, base_url: str) -> dict:
    return create_checkout_for_sku(user_id, pack_key, base_url=base_url)


def apply_full_access_purchase(order: dict) -> bool:
    user_id = int(order["user_id"])
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    if plan_is_full_access(user.get("plan"), user_id=user_id):
        return False
    set_plan(user_id, "full")
    refresh_user_opportunities(user_id)
    return True


def revert_full_access_purchase(order: dict) -> bool:
    user_id = int(order["user_id"])
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    if is_user_admin(user_id) or normalize_plan(user.get("plan")) == "grandfathered":
        return False
    if normalize_plan(user.get("plan")) != "full":
        return False
    set_plan(user_id, "free")
    refresh_user_opportunities(user_id)
    return True


def _fulfill_paid_order(order: dict) -> dict:
    kind = str(order.get("kind") or "")
    if kind == ORDER_KIND_FULL_ACCESS:
        upgraded = apply_full_access_purchase(order)
        return {"ok": True, "paid": True, "granted": False, "upgraded": upgraded}
    granted = grant_order_credits(order)
    return {"ok": True, "paid": True, "granted": granted, "upgraded": False}


def _revoke_paid_benefits(order: dict, *, reason: str) -> None:
    if str(order.get("kind") or "") == ORDER_KIND_FULL_ACCESS:
        revert_full_access_purchase(order)
        return
    credits_repo.revoke_order_grant(order, reason=reason)


def process_nowpayments_notification(payload: dict, signature: str) -> dict:
    notification = nowpayments.parse_notification(payload, signature)
    order = credits_repo.get_order_by_provider(
        nowpayments.PROVIDER, notification.provider_order_id,
    )
    if not order:
        raise LookupError("Payment order not found")
    result = {"ok": True, "paid": False, "status": notification.status}
    if notification.status in nowpayments.PAID_STATUSES:
        _validate_paid_amount(order, notification.payload)
        paid_order = credits_repo.mark_order_paid(
            nowpayments.PROVIDER, notification.provider_order_id,
        )
        result = _fulfill_paid_order(paid_order or order)
        result["status"] = notification.status
    elif notification.status in FAILED_STATUSES:
        failed_order = credits_repo.update_order_status(
            nowpayments.PROVIDER,
            notification.provider_order_id,
            notification.status,
        )
        if notification.status == "refunded" and failed_order:
            _revoke_paid_benefits(failed_order, reason="provider_refund")
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
    upgraded = False
    if order["status"] == "paid":
        result = _fulfill_paid_order(order)
        granted = bool(result.get("granted"))
        upgraded = bool(result.get("upgraded"))
    return {"order": order, "granted": granted, "upgraded": upgraded}


def revoke_order_credits(order_id: int, *, reason: str) -> dict:
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("A reason is required")
    order = credits_repo.get_order(order_id)
    if not order:
        raise LookupError("Credit order not found")
    if str(order.get("kind") or "") == ORDER_KIND_FULL_ACCESS:
        reverted = revert_full_access_purchase(order)
        return {"order": order, "revoked_credits": 0, "plan_reverted": reverted}
    revoked = credits_repo.revoke_order_grant(order, reason=clean_reason)
    return {"order": order, "revoked_credits": revoked, "plan_reverted": False}
