#!/usr/bin/env python3
"""Role propagator — discoverable entry. Domain: role_propagator/."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    os.chdir(_ROOT)
    os.execvp("go", ["go", "run", str(_ROOT / "apps" / "role-propagator"), *sys.argv[1:]])
