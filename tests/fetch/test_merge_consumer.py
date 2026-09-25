import pytest

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.core.db import get_connection
from relocation_jobs.fetch import go_results
from relocation_jobs.fetch.merge_consumer import process_pending_row


def _company_id(country_key: str, name: str) -> int:
    row = get_connection().execute(
        "SELECT id FROM companies WHERE country = %s AND lower(name) = lower(%s)",
        (country_key, name),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _insert_error_result(*, company_id: int) -> None:
    conn = get_connection()
    row = conn.execute(
        """
        INSERT INTO fetch_runs (
            user_id, country, company_name, scope, status,
            file_name, started_at, finished_at, concurrency, new_jobs,
            progress_json, activity_json, activity_log_json, log_json
        ) VALUES (
            1, 'uk', NULL, 'country', 'done',
            'uk_companies.json', '2020-01-01T00:00:00+00:00', '2020-01-01T01:00:00+00:00',
            1, 0, '{}', '{}', '[]', '[]'
        ) RETURNING id
        """
    ).fetchone()
    run_id = int(row["id"])
    conn.execute(
        """
        INSERT INTO fetch_http_work (
            fetch_run_id, company_id, country_key, name, ats_type, ats_url, careers_url
        ) VALUES (%s, %s, 'uk', 'Acme Backend Ltd', 'greenhouse', '', '')
        """,
        (run_id, company_id),
    )
    conn.execute(
        """
        INSERT INTO fetch_http_results (
            fetch_run_id, company_id, status, error, jobs_json, fetched_at
        ) VALUES (%s, %s, 'error', 'http 500', NULL, '2020-01-01T00:00:00+00:00')
        """,
        (run_id, company_id),
    )


@pytest.mark.asyncio
async def test_merge_consumer_skips_merge_on_error(seeded_catalog_v2, db):
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    before = len(company.get("matching_jobs") or [])
    _insert_error_result(company_id=_company_id("uk", "Acme Backend Ltd"))
    rows = go_results.list_pending_http_results(limit=5)
    assert len(rows) == 1
    assert rows[0]["status"] == "error"
    await process_pending_row(rows[0])
    go_results.mark_http_result_processed(int(rows[0]["id"]))
    updated = get_company("uk", "Acme Backend Ltd")
    assert updated is not None
    assert updated.get("fetch_problem") is True
    assert len(updated.get("matching_jobs") or []) == before


@pytest.mark.asyncio
async def test_merge_consumer_runs_merge_on_ok(seeded_catalog_v2, db, monkeypatch):
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company_id = _company_id("uk", "Acme Backend Ltd")
    jobs_json = '[{"title":"New Role","url":"https://boards.greenhouse.io/acmebackend/jobs/999","location":"London"}]'
    conn = get_connection()
    row = conn.execute(
        """
        INSERT INTO fetch_runs (
            user_id, country, company_name, scope, status,
            file_name, started_at, finished_at, concurrency, new_jobs,
            progress_json, activity_json, activity_log_json, log_json
        ) VALUES (
            1, 'uk', NULL, 'country', 'done',
            'uk_companies.json', '2020-01-01T00:00:00+00:00', '2020-01-01T01:00:00+00:00',
            1, 0, '{}', '{}', '[]', '[]'
        ) RETURNING id
        """
    ).fetchone()
    run_id = int(row["id"])
    conn.execute(
        """
        INSERT INTO fetch_http_work (
            fetch_run_id, company_id, country_key, name, ats_type, ats_url, careers_url
        ) VALUES (%s, %s, 'uk', 'Acme Backend Ltd', 'greenhouse', '', '')
        """,
        (run_id, company_id),
    )
    conn.execute(
        """
        INSERT INTO fetch_http_results (
            fetch_run_id, company_id, status, error, jobs_json, fetched_at
        ) VALUES (%s, %s, 'ok', NULL, %s, '2020-01-01T00:00:00+00:00')
        """,
        (run_id, company_id, jobs_json),
    )
    called = {"merge": False}

    async def fake_process_company(client, comp, index, total, **kwargs):
        called["merge"] = True
        listed = await kwargs["fetch_board"](client, comp)
        assert len(listed) == 1
        sync_company_board_to_catalog("uk", comp)
        return "merged", 1

    monkeypatch.setattr(
        "relocation_jobs.fetch.merge_consumer.process_company",
        fake_process_company,
    )
    rows = go_results.list_pending_http_results(limit=5)
    await process_pending_row(rows[0])
    assert called["merge"] is True
