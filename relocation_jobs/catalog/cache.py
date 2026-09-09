from __future__ import annotations

from relocation_jobs.core.location_tags import invalidate_country_labels_cache


def invalidate_country_cache(country_key: str | None = None) -> None:
    invalidate_country_labels_cache()
