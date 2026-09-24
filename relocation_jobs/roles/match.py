from __future__ import annotations


def job_is_default_match(job: dict) -> bool:
    raw = job.get("matches_default_filter")
    if raw is None:
        return True
    return bool(int(raw))
