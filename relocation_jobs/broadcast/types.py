from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapacityLimits:
    company_slots: int | None
    jobs_per_company: int | None
    total_position_budget: int | None

    @property
    def unlimited(self) -> bool:
        return (
            self.company_slots is None
            and self.jobs_per_company is None
            and self.total_position_budget is None
        )


@dataclass(frozen=True)
class PositionAssignment:
    period_key: str
    country: str
    company_name: str
    job_key: str
    job_url: str
    job_title: str
    assigned_at: str
    consumed_at: str | None = None


@dataclass(frozen=True)
class BoardCapacityMeta:
    company_slots_used: int
    company_slots_cap: int | None
    positions_used: int
    positions_budget: int | None
    jobs_per_company_peek: int | None
    board_capped: bool
    positions_capped: bool
    upgrade_available: bool
    upgrade_reason: str | None = None
    position_period: str | None = None
    credits_promotional: int = 0
    credits_purchased: int = 0
    credits_total: int = 0
    credits_next_reset_at: str | None = None

    def as_dict(self) -> dict:
        return {
            "company_slots_used": self.company_slots_used,
            "company_slots_cap": self.company_slots_cap,
            "positions_used": self.positions_used,
            "positions_budget": self.positions_budget,
            "jobs_per_company_peek": self.jobs_per_company_peek,
            "board_capped": self.board_capped,
            "positions_capped": self.positions_capped,
            "upgrade_available": self.upgrade_available,
            "upgrade_reason": self.upgrade_reason,
            "position_period": self.position_period,
            "credits_promotional": self.credits_promotional,
            "credits_purchased": self.credits_purchased,
            "credits_total": self.credits_total,
            "credits_next_reset_at": self.credits_next_reset_at,
        }


@dataclass(frozen=True)
class RevealEvent:
    country: str
    company_name: str
    kind: str
    job_url: str
    job_key: str = ""
    job_title: str = ""
