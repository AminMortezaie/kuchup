from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ec2_app_deploy.sh"


def _active_lines() -> list[str]:
    lines = []
    for raw in SCRIPT.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def test_deploy_script_is_strict_bash():
    text = SCRIPT.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


def test_deploy_script_never_prunes_volumes_or_pg():
    joined = "\n".join(_active_lines())
    assert "volume prune" not in joined
    assert "system prune" not in joined
    assert "docker rm -v pg" not in joined
    assert "docker stop pg" not in joined
    assert "docker rm -f pg" not in joined
    assert "docker volume rm" not in joined


def test_protected_objects_include_pg_and_pgdata():
    text = SCRIPT.read_text()
    assert "PROTECTED_CONTAINERS=" in text
    assert "PROTECTED_VOLUMES=" in text
    assert "pgdata" in text


def test_image_hash_includes_dockerignore():
    text = SCRIPT.read_text()
    assert ".dockerignore" in text
    assert "Dockerfile.ec2-worker-playwright" in text


def test_frontend_skip_does_not_use_pipefail_find_grep():
    text = SCRIPT.read_text()
    assert "_sources_newer_than" not in text
    assert "_content_hash" in text
    assert ".source-hash" in text


def test_playwright_sidecar_is_opt_in_and_dockerfile_gated():
    text = SCRIPT.read_text()
    assert "DEPLOY_PLAYWRIGHT_WORKER" in text
    assert "PLAYWRIGHT_WORKER_DOCKERFILE" in text
    assert "start_playwright_worker_container" in text


def test_default_worker_run_does_not_force_http_kind():
    text = SCRIPT.read_text()
    assert "Starting fetch worker container..." in text
    worker_block = text.split("Starting fetch worker container...", 1)[1]
    worker_block = worker_block.split("start_playwright_worker_container", 1)[0]
    assert "FETCH_WORKER_KIND=http" not in worker_block


def test_check_local_exits_zero_without_secrets():
    proc = subprocess.run(
        [str(SCRIPT), "check", "--local"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "no rsync, no docker writes" in out
    assert "panel input hash:" in out
    assert "worker input hash:" in out
