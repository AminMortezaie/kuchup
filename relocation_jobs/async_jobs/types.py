from __future__ import annotations

from dataclasses import dataclass
from typing import Union

MSG_RECONCILE_USER = "user"
MSG_RECONCILE_COUNTRY = "country"
MSG_REPLACE = "replace"


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


@dataclass(frozen=True)
class ReplaceAssignment:
    user_id: int
    country: str
    company_name: str
    source_job_key: str = ""

    def to_payload(self) -> dict:
        return {
            "type": MSG_REPLACE,
            "user_id": int(self.user_id),
            "country": (self.country or "").strip().lower(),
            "company_name": (self.company_name or "").strip(),
            "source_job_key": (self.source_job_key or "").strip(),
        }


JobMessage = Union[ReconcileUserOpportunities, ReconcileCountryOpportunities, ReplaceAssignment]
