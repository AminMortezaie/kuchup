from __future__ import annotations

from dataclasses import dataclass

MSG_RECONCILE_USER = "user"
MSG_RECONCILE_COUNTRY = "country"


@dataclass(frozen=True)
class ReconcileUserOpportunities:
    user_id: int

    def to_payload(self) -> dict:
        return {"type": MSG_RECONCILE_USER, "user_id": int(self.user_id)}


@dataclass(frozen=True)
class ReconcileCountryOpportunities:
    country: str

    def to_payload(self) -> dict:
        return {
            "type": MSG_RECONCILE_COUNTRY,
            "country": (self.country or "").strip().lower(),
        }


def parse_message(body: dict) -> ReconcileUserOpportunities | ReconcileCountryOpportunities:
    message_type = (body.get("type") or "").strip().lower()
    if message_type == MSG_RECONCILE_USER:
        return ReconcileUserOpportunities(user_id=int(body["user_id"]))
    if message_type == MSG_RECONCILE_COUNTRY:
        country = (body.get("country") or "").strip().lower()
        if not country:
            raise ValueError("country message missing country")
        return ReconcileCountryOpportunities(country=country)
    raise ValueError(f"Unknown async job message type: {message_type}")
