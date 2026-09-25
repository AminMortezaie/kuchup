import os
import subprocess
from pathlib import Path

import pytest

from relocation_jobs.core.db import get_connection
from relocation_jobs.fetch import repo as fetch_repo


ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "target" / "fetch-scheduler"
INTEGRATION = os.environ.get("GO_FETCH_INTEGRATION") == "1"


@pytest.fixture(scope="module")
def go_scheduler_binary():
    out = BINARY
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["go", "build", "-o", str(out), "./apps/ats-scrape"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return out


@pytest.mark.integration
@pytest.mark.skipif(
    not INTEGRATION,
    reason="Set GO_FETCH_INTEGRATION=1 and a TCP DATABASE_URL to run Go scheduler subprocess test",
)
def test_go_scheduler_once_writes_run_work_and_results(
    seeded_catalog_v2,
    db,
    go_scheduler_binary,
    monkeypatch,
):
    conn = get_connection()
    conn.execute(
        """
        DELETE FROM matching_jobs
        WHERE company_id IN (
            SELECT id FROM companies
            WHERE country = 'uk' AND lower(name) != lower('Acme Backend Ltd')
        )
        """
    )
    conn.execute(
        """
        DELETE FROM companies
        WHERE country = 'uk' AND lower(name) != lower('Acme Backend Ltd')
        """
    )
    monkeypatch.setenv("FETCH_SCHEDULE_ENABLED", "1")
    monkeypatch.setenv("FETCH_SCHEDULE_COUNTRIES", "uk")
    monkeypatch.setenv("FETCH_HTTP_POOL_SIZE", "4")
    db_url = os.environ.get("DATABASE_URL")
    assert db_url
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    proc = subprocess.run(
        [str(go_scheduler_binary), "--once"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    running = fetch_repo.get_running_fetch_run()
    assert running is None
    conn = get_connection()
    run = conn.execute(
        """
        SELECT id, status FROM fetch_runs
        WHERE country = 'uk' AND scope = 'country'
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    assert run is not None
    assert run["status"] == "done"
    run_id = int(run["id"])
    work_count = conn.execute(
        "SELECT COUNT(*) AS n FROM fetch_http_work WHERE fetch_run_id = %s",
        (run_id,),
    ).fetchone()["n"]
    result_count = conn.execute(
        "SELECT COUNT(*) AS n FROM fetch_http_results WHERE fetch_run_id = %s",
        (run_id,),
    ).fetchone()["n"]
    assert work_count > 0
    assert result_count == work_count
