from __future__ import annotations

from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch import state as fetch_state
from relocation_jobs.users.repo import get_user_by_username


def _start_run(*, company: str | None = None) -> int:
    fetch_state.reset_for_tests()
    user_id = get_user_by_username("admin")["id"]
    return fetch_state.reset_for_run(
        user_id=user_id,
        country="uk",
        file_name="uk.json",
        concurrency=1,
        company=company,
    )


def test_finish_run_skips_already_finalized_run(db):
    del db
    run_id = _start_run()
    fetch_state.finish_run(run_id, exit_code=0, cancelled=False, result_line="Done")
    fetch_state.finish_run(run_id, exit_code=1, cancelled=False, result_line="Nope")
    user_id = get_user_by_username("admin")["id"]
    row = fetch_repo.list_user_fetch_runs(user_id, country="uk", limit=1)[0]
    assert row["exit_code"] == 0
    assert row["result_line"] == "Done"


def test_reset_for_run_clears_previous_review_jobs(db):
    del db
    run_id = _start_run(company="Acme")
    fetch_state.set_review_jobs(run_id, {
        "included": [{"title": "Old", "url": "https://example.com/old"}],
        "filtered": [],
    })
    fetch_state.finish_run(run_id, exit_code=0, cancelled=False)
    run_id = fetch_state.reset_for_run(
        user_id=get_user_by_username("admin")["id"],
        country="nl",
        file_name="nl.json",
        concurrency=1,
        company="Swisslog",
    )
    status = fetch_state.build_fetch_status()
    assert run_id == status["run_id"]
    assert status["running"] is True
    assert status["company"] == "Swisslog"
    assert status["review_jobs"] is None
    assert status["log"] == []
    assert status["last_fetch_run"] is None


def test_update_progress_ignores_stale_run_id(db):
    del db
    run_id = _start_run()
    fetch_state.update_progress(run_id + 99, {"current": 9, "total": 10})
    status = fetch_state.build_fetch_status()
    assert int(status["progress"].get("current") or 0) == 0


def test_append_log_drops_lines_past_cap(db, monkeypatch):
    del db
    monkeypatch.setattr("relocation_jobs.fetch.repo.UI_LOG_MAX_LINES", 5)
    run_id = _start_run()
    for i in range(8):
        fetch_state.append_log(run_id, f"line-{i}")
    assert fetch_state.build_fetch_status()["log"] == [
        "line-3",
        "line-4",
        "line-5",
        "line-6",
        "line-7",
    ]
