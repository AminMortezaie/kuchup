from __future__ import annotations

import pytest
import respx
from httpx import Response

from relocation_jobs.scrape.boards.ashby import ashby_job_board_api_url
from relocation_jobs.scrape.boards.greenhouse import greenhouse_job_detail_api_url
from relocation_jobs.scrape.listing_status import (
    ListingStatus,
    classify_http_result,
    next_listing_check_state,
    probe_listing,
)


def test_classify_404_closed():
    assert classify_http_result(404, "missing") is ListingStatus.CLOSED


def test_classify_410_closed():
    assert classify_http_result(410, "") is ListingStatus.CLOSED


def test_classify_429_unknown():
    assert classify_http_result(429, "slow down") is ListingStatus.UNKNOWN


def test_classify_500_unknown():
    assert classify_http_result(500, "error") is ListingStatus.UNKNOWN


def test_classify_empty_200_unknown():
    assert classify_http_result(200, "  ") is ListingStatus.UNKNOWN


def test_classify_200_closed_copy():
    html = "<p>This position has been filled.</p>"
    assert classify_http_result(200, html) is ListingStatus.CLOSED


def test_classify_200_open():
    html = "<p>We are hiring a backend engineer to build APIs.</p>"
    assert classify_http_result(200, html) is ListingStatus.OPEN


def test_next_state_unknown_does_not_increment():
    misses, closed_at = next_listing_check_state(
        1, ListingStatus.UNKNOWN, closed_at="", now="2026-09-07T00:00:00+00:00", threshold=2,
    )
    assert misses == 1
    assert closed_at == ""


def test_next_state_open_resets_misses_keeps_closed_at():
    misses, closed_at = next_listing_check_state(
        2, ListingStatus.OPEN, closed_at="2026-09-01", now="2026-09-07T00:00:00+00:00", threshold=2,
    )
    assert misses == 0
    assert closed_at == "2026-09-01"


def test_next_state_two_misses_sets_closed_at():
    first, closed = next_listing_check_state(
        0, ListingStatus.CLOSED, closed_at="", now="t1", threshold=2,
    )
    assert first == 1
    assert closed == ""
    second, closed = next_listing_check_state(
        first, ListingStatus.CLOSED, closed_at=closed, now="t2", threshold=2,
    )
    assert second == 2
    assert closed == "t2"


@pytest.mark.asyncio
@respx.mock
async def test_probe_greenhouse_404_closed():
    url = "https://boards.greenhouse.io/acmebackend/jobs/123456"
    respx.get(greenhouse_job_detail_api_url("acmebackend", "123456", eu=False)).mock(
        return_value=Response(404),
    )
    respx.get(greenhouse_job_detail_api_url("acmebackend", "123456", eu=True)).mock(
        return_value=Response(404),
    )
    import httpx

    async with httpx.AsyncClient() as client:
        assert await probe_listing(client, url, "greenhouse") is ListingStatus.CLOSED


@pytest.mark.asyncio
@respx.mock
async def test_probe_greenhouse_200_with_content_open():
    url = "https://boards.greenhouse.io/acmebackend/jobs/123456"
    respx.get(greenhouse_job_detail_api_url("acmebackend", "123456", eu=False)).mock(
        return_value=Response(200, json={"content": "<p>Build APIs in Go.</p>"}),
    )
    import httpx

    async with httpx.AsyncClient() as client:
        assert await probe_listing(client, url, "greenhouse") is ListingStatus.OPEN


@pytest.mark.asyncio
@respx.mock
async def test_probe_generic_closed_copy():
    url = "https://example.com/jobs/1"
    respx.get(url).mock(
        return_value=Response(200, text="<p>This job is no longer available.</p>"),
    )
    import httpx

    async with httpx.AsyncClient() as client:
        assert await probe_listing(client, url, "generic") is ListingStatus.CLOSED


@pytest.mark.asyncio
@respx.mock
async def test_probe_ashby_missing_from_board_closed():
    url = "https://jobs.ashbyhq.com/acme/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    respx.get(ashby_job_board_api_url("acme")).mock(
        return_value=Response(200, json={"jobs": [{"id": "other", "jobUrl": "https://x"}]}),
    )
    import httpx

    async with httpx.AsyncClient() as client:
        assert await probe_listing(client, url, "ashby") is ListingStatus.CLOSED
