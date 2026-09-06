from __future__ import annotations

import pytest

from relocation_jobs.catalog.cache import invalidate_country_cache
from relocation_jobs.catalog.repo import (
    apply_listing_check_results,
    get_company,
    list_open_jobs_for_listing_check,
)
from relocation_jobs.fetch.listing_check import check_open_listings
from relocation_jobs.scrape.listing_status import ListingStatus


@pytest.mark.asyncio
async def test_two_misses_sets_closed_at(seeded_catalog_v2, monkeypatch):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    url = company["matching_jobs"][0]["url"]

    async def always_closed(_client, _url, _ats=None):
        return ListingStatus.CLOSED

    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.probe_listing",
        always_closed,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.list_open_jobs_for_listing_check",
        lambda limit: [
            row for row in list_open_jobs_for_listing_check(limit) if row["url"] == url
        ],
    )

    first = await check_open_listings(None, limit=20, concurrency=1, threshold=2)
    assert first["closed"] == 0
    rows = [row for row in list_open_jobs_for_listing_check(50) if row["url"] == url]
    assert rows
    assert rows[0]["listing_misses"] == 1
    assert not rows[0]["closed_at"]

    second = await check_open_listings(None, limit=20, concurrency=1, threshold=2)
    assert second["closed"] == 1
    still_open = [row for row in list_open_jobs_for_listing_check(50) if row["url"] == url]
    assert still_open == []
    reloaded = get_company("uk", "Acme Backend Ltd")
    match = next(job for job in reloaded["matching_jobs"] if job["url"] == url)
    assert match["closed_at"]
    assert match["listing_misses"] == 2


@pytest.mark.asyncio
async def test_unknown_does_not_increment(seeded_catalog_v2, monkeypatch):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    url = company["matching_jobs"][0]["url"]

    async def always_unknown(_client, _url, _ats=None):
        return ListingStatus.UNKNOWN

    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.probe_listing",
        always_unknown,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.list_open_jobs_for_listing_check",
        lambda limit: [
            row for row in list_open_jobs_for_listing_check(limit) if row["url"] == url
        ],
    )
    result = await check_open_listings(None, limit=20, concurrency=1, threshold=2)
    assert result["unknown"] == 1
    assert result["closed"] == 0
    rows = [row for row in list_open_jobs_for_listing_check(50) if row["url"] == url]
    assert rows[0]["listing_misses"] == 0


@pytest.mark.asyncio
async def test_open_resets_misses(seeded_catalog_v2, monkeypatch):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    url = company["matching_jobs"][0]["url"]
    job_id = next(
        row["id"] for row in list_open_jobs_for_listing_check(50) if row["url"] == url
    )
    apply_listing_check_results([{
        "id": job_id,
        "listing_misses": 1,
        "closed_at": "",
        "country": "uk",
    }])

    async def always_open(_client, _url, _ats=None):
        return ListingStatus.OPEN

    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.probe_listing",
        always_open,
    )
    monkeypatch.setattr(
        "relocation_jobs.fetch.listing_check.list_open_jobs_for_listing_check",
        lambda limit: [
            row for row in list_open_jobs_for_listing_check(limit) if row["url"] == url
        ],
    )
    result = await check_open_listings(None, limit=20, concurrency=1, threshold=2)
    assert result["open"] == 1
    rows = [row for row in list_open_jobs_for_listing_check(50) if row["url"] == url]
    assert rows[0]["listing_misses"] == 0
    assert rows[0]["closed_at"] == ""


def test_apply_listing_check_invalidates_cache(seeded_catalog_v2, monkeypatch):
    del seeded_catalog_v2
    cleared: list[str | None] = []

    def fake_invalidate(country_key=None):
        cleared.append(country_key)

    monkeypatch.setattr(
        "relocation_jobs.catalog.repo.invalidate_country_cache",
        fake_invalidate,
    )
    job = list_open_jobs_for_listing_check(1)[0]
    apply_listing_check_results([{
        "id": job["id"],
        "listing_misses": 1,
        "closed_at": "",
        "country": job["country"],
    }])
    assert job["country"] in cleared
    invalidate_country_cache()
