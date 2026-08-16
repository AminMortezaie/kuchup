from __future__ import annotations

from relocation_jobs.broadcast.types import CapacityLimits


def can_consume_position(
    limits: CapacityLimits,
    *,
    positions_used: int,
) -> bool:
    return (
        limits.total_position_budget is None
        or positions_used < limits.total_position_budget
    )


def replacement_allowed(limits: CapacityLimits, *, positions_used: int) -> bool:
    if limits.unlimited:
        return True
    return (
        limits.total_position_budget is None
        or positions_used < limits.total_position_budget
    )
