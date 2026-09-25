#!/usr/bin/env python3
"""Follower: merge Go HTTP fetch results into matching_jobs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from relocation_jobs.fetch.merge_consumer import main

if __name__ == "__main__":
    raise SystemExit(main())
