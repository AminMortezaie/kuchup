from __future__ import annotations

import structlog
from structlog.testing import capture_logs

from relocation_jobs.core.log import configure_logging
from relocation_jobs.fetch.log import bind_fetch_log_context, log_event, log_http_exchange

_CAPTURE_PROCESSORS = [structlog.contextvars.merge_contextvars]


def test_fetch_log_event_includes_context():
    configure_logging()
    structlog.contextvars.clear_contextvars()
    with capture_logs(processors=_CAPTURE_PROCESSORS) as entries:
        log_event(
            "single-company fetch worker started",
            run_id=12,
            country="uk",
            company="Acme Backend Ltd",
            scope="company",
        )
    row = entries[0]
    assert row["event"] == "single-company fetch worker started"
    assert row["run_id"] == 12
    assert row["country"] == "uk"
    assert row["company"] == "Acme Backend Ltd"
    assert row["scope"] == "company"


def test_fetch_http_exchange_logs_job_url_and_bodies():
    configure_logging()
    structlog.contextvars.clear_contextvars()
    bind_fetch_log_context(run_id=7, company="Acme", scope="company", country="uk")
    with capture_logs(processors=_CAPTURE_PROCESSORS) as entries:
        log_http_exchange(
            kind="job",
            method="GET",
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs/42",
            job_url="https://boards.greenhouse.io/acme/jobs/42",
            job_title="Backend Engineer",
            response_status=200,
            response_body='{"content":"<p>Visa sponsorship available</p>"}',
            response_bytes=48,
        )
    row = entries[0]
    assert row["event"] == "HTTP GET job posting"
    assert row["run_id"] == 7
    assert row["country"] == "uk"
    assert row["company"] == "Acme"
    assert row["job_url"] == "https://boards.greenhouse.io/acme/jobs/42"
    assert row["job_title"] == "Backend Engineer"
    assert row["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/42"
    assert row["response_status"] == 200
    assert "Visa sponsorship" in row["response_body"]
