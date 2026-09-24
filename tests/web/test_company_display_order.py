from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS_TEST = Path(__file__).resolve().parent / "js" / "company_display_order.test.mjs"


def test_company_display_order_stable_during_interaction():
    result = subprocess.run(
        ["node", "--test", str(JS_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
