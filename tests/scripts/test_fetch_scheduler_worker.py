import os
import subprocess
import sys
from pathlib import Path


def test_fetch_scheduler_worker_refuses_http_kind():
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["FETCH_WORKER_KIND"] = "http"
    env.pop("FETCH_ALLOW_PYTHON_HTTP_SCHEDULER", None)
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "fetch_scheduler_worker.py")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "Go worker" in proc.stderr or "Go worker" in proc.stdout
