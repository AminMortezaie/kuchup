from __future__ import annotations

from collections.abc import Callable

from relocation_jobs.positions.types import PositionBucket, PositionFilters, PositionView, TrackingFlags
from relocation_jobs.shared.predicates import all_of

_BUCKET_RULES: tuple[
    tuple[Callable[[TrackingFlags], bool], PositionBucket],
    ...,
] = (
    (lambda flags: flags.not_for_me, PositionBucket.NOT_FOR_ME),
    (lambda flags: flags.rejected, PositionBucket.REJECTED),
)

_POSITION_FILTER_RULES: tuple[Callable[[tuple[TrackingFlags, PositionFilters]], bool], ...] = (
    lambda ctx: not (ctx[1].hide_applied and ctx[0].applied),
    lambda ctx: not (ctx[1].hide_rejected and ctx[0].rejected),
    lambda ctx: not (ctx[1].applied_only and not ctx[0].applied),
    lambda ctx: not (ctx[1].rejected_only and not ctx[0].rejected),
    lambda ctx: not (ctx[1].looking_to_apply_only and not ctx[0].looking_to_apply),
)


def derive_bucket(flags: TrackingFlags) -> PositionBucket:
    for matches, bucket in _BUCKET_RULES:
        if matches(flags):
            return bucket
    return PositionBucket.JOBS


def orphan_reinject_eligible(flags: TrackingFlags) -> bool:
    return flags.has_active_tracking()


def position_view_from_row(row: dict | None) -> PositionView:
    flags = TrackingFlags.from_row(row)
    return PositionView(
        flags=flags,
        bucket=derive_bucket(flags),
    )


def passes_position_filters(flags: TrackingFlags, filters: PositionFilters) -> bool:
    return all_of((flags, filters), _POSITION_FILTER_RULES)
