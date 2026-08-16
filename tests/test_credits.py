from __future__ import annotations

import hashlib
import hmac
import json

from relocation_jobs.credits import repo
from relocation_jobs.credits.service import credit_balance, spend_for_operation
from relocation_jobs.credits.types import CreditGrantKind, CreditOperation
from relocation_jobs.payments.service import process_nowpayments_notification
from relocation_jobs.users.repo import create_user


def _user(name: str) -> dict:
    return create_user(
        name,
        email=f"{name}@example.com",
        google_sub=f"sub-{name}",
    )


def test_monthly_grant_is_idempotent(db):
    user = _user("credit-monthly")
    first = credit_balance(int(user["id"]))
    second = credit_balance(int(user["id"]))
    assert first.total == 30
    assert second.total == 30
    assert len(repo.list_ledger(int(user["id"]))) == 1


def test_spend_is_atomic_and_idempotent(db):
    user = _user("credit-spend")
    uid = int(user["id"])
    first = spend_for_operation(
        uid,
        CreditOperation.ROLE_REPLACEMENT,
        idempotency_key="role:one",
    )
    duplicate = spend_for_operation(
        uid,
        CreditOperation.ROLE_REPLACEMENT,
        idempotency_key="role:one",
    )
    assert first == {"spent": True, "deduplicated": False, "cost": 1, "balance": 29}
    assert duplicate == {"spent": True, "deduplicated": True, "cost": 1, "balance": 29}
    assert credit_balance(uid).total == 29


def test_promotional_credits_are_spent_before_purchased(db):
    user = _user("credit-ordering")
    uid = int(user["id"])
    credit_balance(uid)
    repo.create_grant(
        uid,
        kind=CreditGrantKind.PURCHASED,
        source_key="purchase:test",
        credits=50,
        expires_at=None,
    )
    for index in range(30):
        spend_for_operation(
            uid,
            CreditOperation.ROLE_REPLACEMENT,
            idempotency_key=f"role:{index}",
        )
    balance = credit_balance(uid)
    assert balance.promotional == 0
    assert balance.purchased == 50


def test_insufficient_balance_does_not_write_spend(db):
    user = _user("credit-empty")
    uid = int(user["id"])
    credit_balance(uid)
    result = repo.spend_credits(
        uid,
        cost=31,
        operation="test",
        idempotency_key="too-many",
    )
    assert result["spent"] is False
    assert all(row["idempotency_key"] != "too-many" for row in repo.list_ledger(uid))


def test_expired_promotional_grant_records_ledger_event(db):
    user = _user("credit-expiry")
    uid = int(user["id"])
    repo.create_grant(
        uid,
        kind=CreditGrantKind.MONTHLY,
        source_key="monthly:2020-01",
        credits=12,
        expires_at="2020-02-01T00:00:00+00:00",
    )
    balance = credit_balance(uid)
    assert balance.promotional == 30
    assert any(row["event_type"] == "expire" for row in repo.list_ledger(uid))


def test_paid_notification_grants_once(db, monkeypatch):
    user = _user("credit-payment")
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
        provider_order_id="invoice-1",
        checkout_url="https://example.com/pay",
    )
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    payload = {
        "invoice_id": "invoice-1",
        "payment_status": "finished",
        "price_amount": 4.99,
        "price_currency": "usd",
        "actually_paid": 4.99,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(b"secret", canonical, hashlib.sha512).hexdigest()
    first = process_nowpayments_notification(payload, signature)
    second = process_nowpayments_notification(payload, signature)
    assert first["paid"] is True
    assert second["deduplicated"] is True
    assert repo.credit_audit()["ok"] is True
    assert credit_balance(uid).purchased == 50

    refunded = {**payload, "payment_status": "refunded"}
    refund_body = json.dumps(refunded, separators=(",", ":"), sort_keys=True).encode()
    refund_signature = hmac.new(b"secret", refund_body, hashlib.sha512).hexdigest()
    process_nowpayments_notification(refunded, refund_signature)
    assert credit_balance(uid).purchased == 0
