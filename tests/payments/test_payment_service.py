from __future__ import annotations

import hashlib
import hmac

import pytest

from relocation_jobs.credits import repo
from relocation_jobs.credits.service import credit_balance
from relocation_jobs.payments.nowpayments import canonical_ipn_body
from relocation_jobs.payments.service import (
    create_checkout_for_sku,
    process_nowpayments_notification,
)
from relocation_jobs.payments.types import ORDER_KIND_FULL_ACCESS
from relocation_jobs.users.repo import create_user, get_user_by_id


def _user(name: str, **kwargs) -> dict:
    return create_user(
        name,
        email=f"{name}@example.com",
        google_sub=f"sub-{name}",
        **kwargs,
    )


def _sign(payload: dict, secret: str = "secret") -> str:
    return hmac.new(secret.encode(), canonical_ipn_body(payload), hashlib.sha512).hexdigest()


def _paid_payload(invoice_id: str, amount: float = 4.99) -> dict:
    return {
        "invoice_id": invoice_id,
        "payment_status": "finished",
        "price_amount": amount,
        "price_currency": "usd",
    }


def test_amount_mismatch_does_not_grant(db, monkeypatch):
    user = _user("pay-mismatch")
    uid = int(user["id"])
    order_id = repo.create_order(
        uid,
        pack_key="starter",
        credits=50,
        price_minor=499,
        currency="USD",
        provider="nowpayments",
    )
    repo.update_order_checkout(
        order_id,
        provider_order_id="invoice-mismatch",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = _paid_payload("invoice-mismatch", amount=1.00)
    with pytest.raises(ValueError, match="does not match"):
        process_nowpayments_notification(payload, _sign(payload))
    assert credit_balance(uid).purchased == 0


def test_partially_paid_does_not_grant(db, monkeypatch):
    user = _user("pay-partial")
    uid = int(user["id"])
    order_id = repo.create_order(
        uid,
        pack_key="starter",
        credits=50,
        price_minor=499,
        currency="USD",
        provider="nowpayments",
    )
    repo.update_order_checkout(
        order_id,
        provider_order_id="invoice-partial",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = {**_paid_payload("invoice-partial"), "payment_status": "partially_paid"}
    result = process_nowpayments_notification(payload, _sign(payload))
    assert result["paid"] is False
    assert credit_balance(uid).purchased == 0


def test_full_access_ipn_sets_plan_once(db, monkeypatch):
    user = _user("pay-full")
    uid = int(user["id"])
    rematch = []
    monkeypatch.setattr(
        "relocation_jobs.payments.service.refresh_user_opportunities",
        lambda user_id: rematch.append(user_id) or {"user_id": user_id},
    )
    order_id = repo.create_order(
        uid,
        pack_key="full_access",
        credits=0,
        price_minor=2900,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_FULL_ACCESS,
    )
    repo.update_order_checkout(
        order_id,
        provider_order_id="invoice-full",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = _paid_payload("invoice-full", amount=29.00)
    first = process_nowpayments_notification(payload, _sign(payload))
    second = process_nowpayments_notification(payload, _sign(payload))
    assert first["paid"] is True
    assert first["upgraded"] is True
    assert second["deduplicated"] is True
    assert get_user_by_id(uid)["plan"] == "full"
    assert rematch == [uid]
    assert repo.credit_audit()["ok"] is True


def test_full_access_refund_returns_free(db, monkeypatch):
    user = _user("pay-full-refund")
    uid = int(user["id"])
    monkeypatch.setattr(
        "relocation_jobs.payments.service.refresh_user_opportunities",
        lambda user_id: {"user_id": user_id},
    )
    order_id = repo.create_order(
        uid,
        pack_key="full_access",
        credits=0,
        price_minor=2900,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_FULL_ACCESS,
    )
    repo.update_order_checkout(
        order_id,
        provider_order_id="invoice-full-refund",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    paid = _paid_payload("invoice-full-refund", amount=29.00)
    process_nowpayments_notification(paid, _sign(paid))
    refunded = {**paid, "payment_status": "refunded"}
    process_nowpayments_notification(refunded, _sign(refunded))
    assert get_user_by_id(uid)["plan"] == "free"


def test_checkout_for_sku_uses_public_base_url(db, monkeypatch):
    user = _user("pay-checkout-url")
    monkeypatch.setenv("NOWPAYMENTS_API_KEY", "key")
    monkeypatch.setenv("PANEL_PUBLIC_BASE_URL", "https://kuchup.com")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "inv-url", "invoice_url": "https://now.test/starter"}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return Response()

    monkeypatch.setattr("relocation_jobs.payments.nowpayments.httpx.post", fake_post)

    result = create_checkout_for_sku(
        int(user["id"]),
        "starter",
        base_url="http://127.0.0.1:10000/",
    )
    assert result["checkout_url"] == "https://now.test/starter"
    assert captured["json"]["ipn_callback_url"].startswith("https://kuchup.com/")
    assert "credits=success" in captured["json"]["success_url"]


def test_full_access_refund_keeps_grandfathered(db, monkeypatch):
    user = _user("pay-gf", plan="grandfathered")
    uid = int(user["id"])
    monkeypatch.setattr(
        "relocation_jobs.payments.service.refresh_user_opportunities",
        lambda user_id: {"user_id": user_id},
    )
    order_id = repo.create_order(
        uid,
        pack_key="full_access",
        credits=0,
        price_minor=2900,
        currency="USD",
        provider="nowpayments",
        kind=ORDER_KIND_FULL_ACCESS,
    )
    repo.update_order_checkout(
        order_id,
        provider_order_id="invoice-gf",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    paid = _paid_payload("invoice-gf", amount=29.00)
    process_nowpayments_notification(paid, _sign(paid))
    refunded = {**paid, "payment_status": "refunded"}
    process_nowpayments_notification(refunded, _sign(refunded))
    assert get_user_by_id(uid)["plan"] == "grandfathered"
