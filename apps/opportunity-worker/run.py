#!/usr/bin/env python3
"""Opportunity SQS worker — discoverable entry. Ops: scripts/opportunity_sqs_worker.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __name__ == "__main__":
    runpy.run_path(str(_ROOT / "scripts" / "opportunity_sqs_worker.py"), run_name="__main__")
