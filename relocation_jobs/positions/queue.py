from __future__ import annotations


def is_active_application_queue_row(row: dict | None) -> bool:
    if not row:
        return False
    if bool(row.get("applied")):
        return False
    return bool(row.get("pinned")) or bool(row.get("looking_to_apply"))
