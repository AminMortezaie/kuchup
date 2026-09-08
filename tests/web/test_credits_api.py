from __future__ import annotations

from relocation_jobs.users.repo import create_user


def _login(client, user: dict) -> None:
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["username"] = user["username"]


def test_credit_wallet_and_packs_api(client, db):
    user = create_user(
        "credit-api",
        email="credit-api@example.com",
        google_sub="sub-credit-api",
    )
    _login(client, user)
    packs = client.get("/api/credits/packs")
    wallet = client.get("/api/credits?history=1")
    assert packs.status_code == 200
    assert [pack["credits"] for pack in packs.get_json()["packs"]] == [10, 50, 150, 400]
    assert packs.get_json()["packs"][0] == {
        "key": "mini",
        "credits": 10,
        "price_minor": 99,
        "currency": "USD",
        "label": "10 credits",
    }
    assert wallet.status_code == 200
    body = wallet.get_json()
    assert body["balance"]["total"] == 30
    assert body["plan"] == "free"
    assert body["full_access"]["key"] == "full_access"
    assert body["full_access"]["price_minor"] == 2900


def test_credit_checkout_uses_authenticated_user(client, db, monkeypatch):
    user = create_user(
        "credit-checkout",
        email="credit-checkout@example.com",
        google_sub="sub-credit-checkout",
    )
    _login(client, user)
    monkeypatch.setattr(
        "relocation_jobs.web.routes.credits.create_credit_checkout",
        lambda user_id, pack_key, base_url: {
            "order_id": 7,
            "provider": "nowpayments",
            "checkout_url": "https://pay.example/7",
        },
    )
    response = client.post("/api/credits/checkout", json={"pack_key": "starter"})
    assert response.status_code == 201
    assert response.get_json()["checkout_url"] == "https://pay.example/7"


def test_payments_checkout_uses_authenticated_user(client, db, monkeypatch):
    user = create_user(
        "plan-checkout",
        email="plan-checkout@example.com",
        google_sub="sub-plan-checkout",
    )
    _login(client, user)
    monkeypatch.setattr(
        "relocation_jobs.web.routes.payments.create_checkout_for_sku",
        lambda user_id, sku_key, base_url: {
            "order_id": 9,
            "provider": "nowpayments",
            "sku": sku_key,
            "kind": "full_access",
            "checkout_url": "https://pay.example/full",
        },
    )
    response = client.post("/api/payments/checkout", json={"sku": "full_access"})
    assert response.status_code == 201
    assert response.get_json()["checkout_url"] == "https://pay.example/full"
    assert response.get_json()["kind"] == "full_access"


def test_ipn_url_is_reachable_without_secrets(client, db):
    response = client.get("/api/payments/nowpayments/ipn")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_credit_webhook_rejects_unconfigured_provider(client, db, monkeypatch):
    monkeypatch.delenv("NOWPAYMENTS_IPN_SECRET", raising=False)
    response = client.post(
        "/api/payments/nowpayments/ipn",
        json={"invoice_id": "unknown", "payment_status": "finished"},
        headers={"x-nowpayments-sig": "bad"},
    )
    assert response.status_code == 503


def test_credit_webhook_rejects_bad_signature(client, db, monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_IPN_SECRET", "secret")
    response = client.post(
        "/api/payments/nowpayments/ipn",
        json={"invoice_id": "unknown", "payment_status": "finished"},
        headers={"x-nowpayments-sig": "bad"},
    )
    assert response.status_code == 401


def test_admin_can_grant_credits(v2_auth_client, db):
    user = create_user(
        "credit-admin-target",
        email="credit-admin-target@example.com",
        google_sub="sub-credit-admin-target",
    )
    response = v2_auth_client.post(
        f"/api/admin/users/{user['id']}/credits",
        json={"credits": 25, "reason": "support adjustment"},
    )
    assert response.status_code == 200
    assert response.get_json()["wallet"]["balance"]["total"] == 55
