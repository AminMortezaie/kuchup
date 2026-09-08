from __future__ import annotations

from dataclasses import dataclass


ORDER_KIND_CREDITS = "credits"
ORDER_KIND_FULL_ACCESS = "full_access"


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


@dataclass(frozen=True)
class CheckoutSku:
    key: str
    kind: str
    credits: int
    price_minor: int
    currency: str
    label: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "credits": self.credits,
            "price_minor": self.price_minor,
            "currency": self.currency,
            "label": self.label,
        }
