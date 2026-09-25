from __future__ import annotations

from relocation_jobs.shared.coerce import as_bool

APPLICATION_STATE_APPLY = "apply"
APPLICATION_STATE_APPLIED = "applied"
APPLICATION_STATE_REJECTED = "rejected"

APPLICATION_STATES = (
    APPLICATION_STATE_APPLY,
    APPLICATION_STATE_APPLIED,
    APPLICATION_STATE_REJECTED,
)


def is_active_application_queue_row(row: dict | None) -> bool:
    if not row:
        return False
    if as_bool(row.get("applied")) or as_bool(row.get("not_for_me")) or as_bool(row.get("rejected")):
        return False
    return as_bool(row.get("pinned")) or as_bool(row.get("looking_to_apply"))


def is_active_applied_row(row: dict | None) -> bool:
    if not row:
        return False
    if not as_bool(row.get("applied")):
        return False
    if as_bool(row.get("rejected")):
        return False
    if as_bool(row.get("not_for_me")):
        return False
    return True


def is_rejected_application_row(row: dict | None) -> bool:
    if not row:
        return False
    if not as_bool(row.get("rejected")):
        return False
    if as_bool(row.get("not_for_me")):
        return False
    return True
