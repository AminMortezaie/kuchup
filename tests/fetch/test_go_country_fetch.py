from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.fetch.runner import go_country_env


def test_go_country_env_attaches_the_panel_run(monkeypatch):
    monkeypatch.setenv("FETCH_ATS_TYPE", "leftover")
    monkeypatch.delenv("FETCH_HTTP_POOL_SIZE", raising=False)
    env = go_country_env("uk", 17, 99, None, timeout=120)
    assert env["FETCH_SCHEDULE_ENABLED"] == "1"
    assert env["FETCH_SCHEDULE_COUNTRIES"] == "uk"
    assert env["FETCH_RUN_ID"] == "17"
    assert env["FETCH_HTTP_POOL_SIZE"] == str(MAX_CONCURRENCY)
    assert env["FETCH_COUNTRY_TIMEOUT_SECONDS"] == "120"
    assert "FETCH_ATS_TYPE" not in env


def test_ready_result_id_reads_go_signal():
    from relocation_jobs.fetch.runner import ready_result_id

    assert ready_result_id("FETCH_READY 17\n") == 17
    assert ready_result_id("other line") is None


def test_go_country_env_keeps_ats_filter(monkeypatch):
    env = go_country_env("nl", 3, 4, "greenhouse")
    assert env["FETCH_ATS_TYPE"] == "greenhouse"
    assert env["FETCH_HTTP_POOL_SIZE"] == "4"
