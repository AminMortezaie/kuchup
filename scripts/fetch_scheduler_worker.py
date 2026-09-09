#!/usr/bin/env python3
"""Long-running fetch scheduler worker (EC2 or local). Docker/ops entry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from relocation_jobs.fetch.scheduler import main

if __name__ == "__main__":
    raise SystemExit(main())
