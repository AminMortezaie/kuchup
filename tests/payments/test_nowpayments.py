from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from relocation_jobs.payments import nowpayments
from relocation_jobs.payments.nowpayments import canonical_ipn_body, parse_notification


def _sign(payload: dict, secret: str = "secret") -> str:
    return hmac.new(secret.encode(), canonical_ipn_body(payload), hashlib.sha512).hexdigest()


def test_canonical_ipn_sorts_top_level_only():
    payload = {
        "z": 1,
        "a": {"z": 1, "a": 2},
        "invoice_id": "inv-1",
        "payment_status": "finished",
    }
    top_level = canonical_ipn_body(payload)
    recursive = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    assert top_level != recursive
    assert top_level == (
        b'{"a":{"z":1,"a":2},"invoice_id":"inv-1","payment_status":"finished","z":1}'
    )


def test_parse_notification_accepts_provider_signature(monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = {
        "z": 1,
        "a": {"z": 1, "a": 2},
        "invoice_id": "inv-1",
        "payment_status": "finished",
    }
    parsed = parse_notification(payload, _sign(payload))
    assert parsed.provider_order_id == "inv-1"
    assert parsed.status == "finished"


def test_parse_notification_rejects_recursive_sort_signature(monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = {
        "z": 1,
        "a": {"z": 1, "a": 2},
        "invoice_id": "inv-1",
        "payment_status": "finished",
    }
    recursive = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    bad = hmac.new(b"secret", recursive, hashlib.sha512).hexdigest()
    with pytest.raises(PermissionError):
        parse_notification(payload, bad)


def test_create_checkout_uses_public_base_url_and_live_api(monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_API_KEY", "key")
    monkeypatch.setenv("PANEL_PUBLIC_BASE_URL", "https://kuchup.com")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "inv-9", "invoice_url": "https://now.test/pay"}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    session = nowpayments.create_checkout(
        order_id=3,
        price_minor=2900,
        currency="USD",
        description="Kuchup Full Access",
        base_url="http://127.0.0.1:10000/",
        return_query="upgrade",
    )
    assert session.checkout_url == "https://now.test/pay"
    assert captured["url"] == "https://api.nowpayments.io/v1/invoice"
    assert captured["json"]["ipn_callback_url"] == (
        "https://kuchup.com/api/payments/nowpayments/ipn"
    )
    assert captured["json"]["success_url"] == "https://kuchup.com/panel?upgrade=success"


def test_sandbox_api_root(monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_SANDBOX", "1")
    assert nowpayments.api_root() == "https://api-sandbox.nowpayments.io"
