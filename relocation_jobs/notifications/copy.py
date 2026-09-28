from __future__ import annotations


def new_jobs_notification_body(count: int) -> str:
    n = int(count)
    if n == 1:
        return "1 new job found!"
    return f"{n} new jobs found!"
