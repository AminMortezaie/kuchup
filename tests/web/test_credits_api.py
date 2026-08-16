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
    assert [pack["credits"] for pack in packs.get_json()["packs"]] == [50, 150, 400]
    assert wallet.status_code == 200
    assert wallet.get_json()["balance"]["total"] == 30


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
