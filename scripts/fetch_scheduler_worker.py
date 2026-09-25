#!/usr/bin/env python3
"""Legacy Python scheduler — not used by the HTTP fetch worker container."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOGGER = logging.getLogger("relocation_jobs.fetch.scheduler_worker")


def main() -> int:
    kind = (os.environ.get("FETCH_WORKER_KIND") or "").strip().lower()
    allow = os.environ.get("FETCH_ALLOW_PYTHON_HTTP_SCHEDULER", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if kind in ("", "http") and not allow:
        LOGGER.error(
            "HTTP country scheduling runs in the Go worker (/fetch-scheduler). "
            "Set FETCH_ALLOW_PYTHON_HTTP_SCHEDULER=1 only for local debugging."
        )
        return 1
    from relocation_jobs.fetch.scheduler import main as scheduler_main

    return int(scheduler_main())


if __name__ == "__main__":
    raise SystemExit(main())
