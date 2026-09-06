from __future__ import annotations

from relocation_jobs.panel.flatten_jobs import partition_stored_jobs
from relocation_jobs.positions.types import PositionFilters


def test_partition_routes_rejected():
    url = "https://example.com/jobs/1"
    jobs, nfm, rejected, _, _ = partition_stored_jobs(
        [{"url": url, "title": "Eng"}],
        user_id=1,
        job_tracking={("uk", "Co", url): {"rejected": 1}},
        company_name="Co",
        company={"name": "Co", "locations": []},
        country_key="uk",
        country_label="UK",
        status_history={},
        mcp_applications=None,
        visa_only=False,
        position_filters=PositionFilters(),
    )
    assert not jobs
    assert not nfm
    assert len(rejected) == 1
    assert rejected[0]["rejected"] is True


def test_partition_skips_visa_filter():
    jobs, _, _, _, hidden = partition_stored_jobs(
        [{"url": "https://example.com/jobs/1", "visa_sponsorship": False}],
        user_id=None,
        job_tracking={},
        company_name="Co",
        company={"name": "Co", "locations": []},
        country_key="uk",
        country_label="UK",
        status_history={},
        mcp_applications=None,
        visa_only=True,
        position_filters=PositionFilters(),
    )
    assert not jobs
    assert hidden == 1


def test_partition_hides_closed_unengaged():
    url = "https://example.com/jobs/1"
    jobs, nfm, rejected, _, _ = partition_stored_jobs(
        [{"url": url, "title": "Eng", "closed_at": "2026-09-07"}],
        user_id=1,
        job_tracking={},
        company_name="Co",
        company={"name": "Co", "locations": []},
        country_key="uk",
        country_label="UK",
        status_history={},
        mcp_applications=None,
        visa_only=False,
        position_filters=PositionFilters(),
    )
    assert not jobs
    assert not nfm
    assert not rejected


def test_partition_keeps_closed_when_applied():
    url = "https://example.com/jobs/1"
    jobs, nfm, rejected, _, _ = partition_stored_jobs(
        [{"url": url, "title": "Eng", "closed_at": "2026-09-07"}],
        user_id=1,
        job_tracking={("uk", "Co", url): {"applied": 1}},
        company_name="Co",
        company={"name": "Co", "locations": []},
        country_key="uk",
        country_label="UK",
        status_history={},
        mcp_applications=None,
        visa_only=False,
        position_filters=PositionFilters(),
    )
    assert len(jobs) == 1
    assert jobs[0]["closed_at"] == "2026-09-07"
    assert not nfm
    assert not rejected


def test_partition_keeps_closed_when_looking_to_apply():
    url = "https://example.com/jobs/1"
    jobs, _, _, _, _ = partition_stored_jobs(
        [{"url": url, "title": "Eng", "closed_at": "2026-09-07"}],
        user_id=1,
        job_tracking={("uk", "Co", url): {"looking_to_apply": 1}},
        company_name="Co",
        company={"name": "Co", "locations": []},
        country_key="uk",
        country_label="UK",
        status_history={},
        mcp_applications=None,
        visa_only=False,
        position_filters=PositionFilters(),
    )
    assert len(jobs) == 1
    assert jobs[0]["looking_to_apply"] is True
