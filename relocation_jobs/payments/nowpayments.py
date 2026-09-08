from __future__ import annotations

import hashlib
import hmac
import json
import os

import httpx

from relocation_jobs.payments.types import CheckoutSession, PaymentNotification


PROVIDER = "nowpayments"
PAID_STATUSES = frozenset({"confirmed", "finished"})
SANDBOX_API_ROOT = "https://api-sandbox.nowpayments.io"
LIVE_API_ROOT = "https://api.nowpayments.io"
_TRUTHY = frozenset({"1", "true", "yes"})


def configured() -> bool:
    return bool(
        os.environ.get("NOWPAYMENTS_API_KEY", "").strip()
        and os.environ.get("NOWPAYMENTS_IPN_SECRET", "").strip()
    )


def sandbox_enabled() -> bool:
    return os.environ.get("NOWPAYMENTS_SANDBOX", "").strip().lower() in _TRUTHY


def api_root() -> str:
    return SANDBOX_API_ROOT if sandbox_enabled() else LIVE_API_ROOT


def public_base_url(fallback: str = "") -> str:
    configured_url = os.environ.get("PANEL_PUBLIC_BASE_URL", "").strip()
    return (configured_url or fallback).rstrip("/")


def canonical_ipn_body(payload: dict) -> bytes:
    ordered = {key: payload[key] for key in sorted(payload)}
    return json.dumps(ordered, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def create_checkout(
    *,
    order_id: int,
    price_minor: int,
    currency: str,
    description: str,
    base_url: str,
    return_query: str = "credits",
) -> CheckoutSession:
    api_key = os.environ.get("NOWPAYMENTS_API_KEY", "").strip()
    origin = public_base_url(base_url)
    if not api_key or not origin:
        raise RuntimeError("Credit checkout is not configured")
    payload = {
        "price_amount": price_minor / 100,
        "price_currency": currency.lower(),
        "order_id": str(order_id),
        "order_description": description,
        "ipn_callback_url": f"{origin}/api/payments/nowpayments/ipn",
        "success_url": f"{origin}/panel?{return_query}=success",
        "cancel_url": f"{origin}/panel?{return_query}=cancelled",
    }
    response = httpx.post(
        f"{api_root()}/v1/invoice",
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
    expected = hmac.new(secret.encode("utf-8"), canonical_ipn_body(payload), hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise PermissionError("Invalid payment signature")
    provider_order_id = str(
        payload.get("invoice_id") or payload.get("payment_id") or "",
    ).strip()
    status = str(payload.get("payment_status") or "").strip().lower()
    if not provider_order_id or not status:
        raise ValueError("Payment notification is incomplete")
    event_id = hashlib.sha256(canonical_ipn_body(payload)).hexdigest()
    return PaymentNotification(
        event_id=event_id,
        provider_order_id=provider_order_id,
        status=status,
        payload=payload,
    )
