#!/usr/bin/env python3
"""Playwright ATS fetch worker (jibe / atlassian / hibob)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("FETCH_WORKER_KIND", "playwright")
os.environ.setdefault("FETCH_LISTING_CHECK_ENABLED", "0")

from relocation_jobs.fetch.scheduler import main

if __name__ == "__main__":
    raise SystemExit(main())
