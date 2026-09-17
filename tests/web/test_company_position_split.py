from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS_TEST = Path(__file__).resolve().parent / "js" / "company_positions_split.test.mjs"


def test_company_positions_js_active_vs_history_split():
    result = subprocess.run(
        ["node", "--test", str(JS_TEST)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
