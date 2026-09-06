from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CreditGrantKind(str, Enum):
    MONTHLY = "monthly"
    PURCHASED = "purchased"
    SUBSCRIPTION = "subscription"
    ADMIN = "admin"
    REFUND = "refund"


class CreditOperation(str, Enum):
    ROLE_REPLACEMENT = "role_replacement"
    PDF_RENDER = "pdf_render"
    JOB_DESCRIPTION_FETCH = "job_description_fetch"
    APPLICATION_PACK = "application_pack"
    COMPANY_REFRESH = "company_refresh"
    PUBLIC_JOB_SAVE = "public_job_save"


@dataclass(frozen=True)
class CreditPack:
    key: str
    credits: int
    price_minor: int
    currency: str
    label: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "credits": self.credits,
            "price_minor": self.price_minor,
            "currency": self.currency,
            "label": self.label,
        }


@dataclass(frozen=True)
class CreditBalance:
    promotional: int
    purchased: int
    total: int
    next_reset_at: str
    period_key: str

    def as_dict(self) -> dict:
        return {
            "promotional": self.promotional,
            "purchased": self.purchased,
            "total": self.total,
            "next_reset_at": self.next_reset_at,
            "period_key": self.period_key,
        }
