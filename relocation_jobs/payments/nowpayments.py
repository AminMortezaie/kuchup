from __future__ import annotations

import hashlib
import hmac
import json
import os

import httpx

from relocation_jobs.payments.types import CheckoutSession, PaymentNotification


PROVIDER = "nowpayments"
PAID_STATUSES = frozenset({"confirmed", "finished"})


def configured() -> bool:
    return bool(
        os.environ.get("NOWPAYMENTS_API_KEY", "").strip()
        and os.environ.get("NOWPAYMENTS_IPN_SECRET", "").strip()
    )


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def create_checkout(
    *,
    order_id: int,
    price_minor: int,
    currency: str,
    description: str,
    base_url: str,
) -> CheckoutSession:
    api_key = os.environ.get("NOWPAYMENTS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Credit checkout is not configured")
    payload = {
        "price_amount": price_minor / 100,
        "price_currency": currency.lower(),
        "order_id": str(order_id),
        "order_description": description,
        "ipn_callback_url": f"{base_url.rstrip('/')}/api/payments/nowpayments/ipn",
        "success_url": f"{base_url.rstrip('/')}/panel?credits=success",
        "cancel_url": f"{base_url.rstrip('/')}/panel?credits=cancelled",
    }
    response = httpx.post(
        "https://api.nowpayments.io/v1/invoice",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    provider_id = str(body.get("id") or body.get("invoice_id") or "").strip()
    checkout_url = str(body.get("invoice_url") or "").strip()
    if not provider_id or not checkout_url:
        raise RuntimeError("Payment provider returned an incomplete checkout")
    return CheckoutSession(provider_order_id=provider_id, checkout_url=checkout_url)


def parse_notification(payload: dict, signature: str) -> PaymentNotification:
    secret = os.environ.get("NOWPAYMENTS_IPN_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Payment webhook is not configured")
    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(payload),
        hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise PermissionError("Invalid payment signature")
    provider_order_id = str(
        payload.get("invoice_id") or payload.get("payment_id") or "",
    ).strip()
    status = str(payload.get("payment_status") or "").strip().lower()
    if not provider_order_id or not status:
        raise ValueError("Payment notification is incomplete")
    event_id = hashlib.sha256(_canonical_payload(payload)).hexdigest()
    return PaymentNotification(
        event_id=event_id,
        provider_order_id=provider_order_id,
        status=status,
        payload=payload,
    )
