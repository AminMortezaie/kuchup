from __future__ import annotations

import structlog
from structlog.testing import capture_logs

from relocation_jobs.core.log import configure_logging
from relocation_jobs.fetch.log import log_event

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
