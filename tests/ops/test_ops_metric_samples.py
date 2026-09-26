from __future__ import annotations

from datetime import datetime, timezone

from relocation_jobs.core.migrations import _ensure_ops_metric_samples_table
from relocation_jobs.ops.repo import insert_ops_metric_samples
from tests.helpers.postgres_mock import install_postgres_mock


def test_ops_metric_samples_migration_and_insert(monkeypatch):
    fake = install_postgres_mock(monkeypatch)
    _ensure_ops_metric_samples_table(fake)
    at = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
    insert_ops_metric_samples(
        fake,
        [
            (
                at,
                "probe_success",
                {"job": "integrations/blackbox", "instance": "kuchup-ec2"},
                1.0,
            ),
            (
                at,
                "node_memory_MemAvailable_bytes",
                {"job": "integrations/node_exporter", "instance": "kuchup-ec2"},
                512000000.0,
            ),
        ],
    )
    row = fake.execute(
        """
        SELECT metric, labels, value
        FROM ops_metric_samples
        WHERE metric = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        ("probe_success",),
    ).fetchone()
    assert row["metric"] == "probe_success"
    assert row["value"] == 1.0
    assert "blackbox" in row["labels"]
