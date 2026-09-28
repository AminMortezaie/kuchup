#!/usr/bin/env python3
"""Notification worker — discoverable entry. Domain: notification_worker/."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    os.chdir(_ROOT)
    os.execvp("go", ["go", "run", str(_ROOT / "apps" / "notification-worker"), *sys.argv[1:]])
