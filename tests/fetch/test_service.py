from __future__ import annotations

from relocation_jobs.fetch.repo import list_attempts
from relocation_jobs.fetch.types import AttemptStatus


def test_finish_company_attempt_records_error(db):
    from relocation_jobs.fetch import service as fetch_service

    del db
    company = {"name": "Fail Co", "careers_url": "https://fail.example/jobs", "matching_jobs": []}
    attempt_id = fetch_service.start_company_attempt(company, country_key="uk")
    msg, new_count = fetch_service.finish_company_attempt(
        attempt_id,
        company,
        "[1/1] Fail Co — Error: connection refused",
        0,
    )
    assert new_count == 0
    assert "Error:" in msg
    assert company.get("fetch_problem") is None

    rows = list_attempts(country="uk", company_name="Fail Co")
    assert rows[0].status == AttemptStatus.ERROR
    assert rows[0].error_message == "connection refused"


def test_finish_company_attempt_records_ok(db):
    from relocation_jobs.fetch import service as fetch_service

    del db
    company = {
        "name": "Ok Co",
        "careers_url": "https://ok.example/jobs",
        "matching_jobs": [{"url": "https://jobs.example/a", "title": "Eng"}],
    }
    attempt_id = fetch_service.start_company_attempt(company, country_key="uk")
    msg, new_count = fetch_service.finish_company_attempt(
        attempt_id,
        company,
        "[1/1] Ok Co — 1 matching job(s)",
        1,
    )
    assert new_count == 1
    rows = list_attempts(country="uk", company_name="Ok Co")
    assert rows[0].status == AttemptStatus.OK
    assert rows[0].jobs_new == 1
