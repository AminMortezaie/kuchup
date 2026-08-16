from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutSession:
    provider_order_id: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentNotification:
    event_id: str
    provider_order_id: str
    status: str
    payload: dict
