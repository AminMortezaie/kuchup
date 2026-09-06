#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from relocation_jobs.core.log import configure_logging
from relocation_jobs.core.sqs_client import sqs_enabled
from relocation_jobs.db import init_db
from relocation_jobs.async_jobs.dispatch import poll_once

LOGGER = logging.getLogger("opportunity_sqs_worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll user-opportunity-refresh SQS queue")
    parser.add_argument("--once", action="store_true", help="Process one poll batch and exit")
    parser.add_argument("--wait-seconds", type=int, default=10)
    parser.add_argument("--max-messages", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    configure_logging()
    init_db()
    if not sqs_enabled():
        LOGGER.error("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL is not set")
        return 2

    while True:
        result = poll_once(
            max_messages=args.max_messages,
            wait_seconds=args.wait_seconds,
        )
        LOGGER.info("poll result=%s", result)
        if args.once:
            return 0 if int(result.get("errors") or 0) == 0 else 1
        time.sleep(max(0.0, args.sleep_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
