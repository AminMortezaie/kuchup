from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable


def insert_ops_metric_samples(
    conn,
    samples: Iterable[tuple[datetime, str, dict[str, Any], float]],
) -> None:
    rows = list(samples)
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO ops_metric_samples (recorded_at, metric, labels, value)
        VALUES (%s, %s, %s::jsonb, %s)
        """,
        [
            (at, metric, json.dumps(labels or {}), value)
            for at, metric, labels, value in rows
        ],
    )
