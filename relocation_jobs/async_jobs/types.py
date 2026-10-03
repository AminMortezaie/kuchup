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
    fetch_run_id: int = 0

    def to_payload(self) -> dict:
        payload = {
            "type": MSG_RECONCILE_COUNTRY,
            "country": (self.country or "").strip().lower(),
        }
        run_id = int(self.fetch_run_id or 0)
        if run_id > 0:
            payload["fetch_run_id"] = run_id
        return payload


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
