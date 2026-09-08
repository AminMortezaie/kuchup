from __future__ import annotations

import json

from relocation_jobs.catalog.repo import get_company, get_public_job_by_slug, sync_company_board_to_catalog
from relocation_jobs.catalog.service import job_posting_json_ld
from relocation_jobs.core.slug import public_job_slug_base
from tests.helpers.seed import merge_and_save_jobs


def _visa_job(seeded_catalog_v2) -> dict:
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    jobs = list(company["matching_jobs"])
    jobs[0]["visa_sponsorship"] = True
    jobs[0]["description_text"] = "<p>Build APIs in Go.</p>"
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", company)
    reloaded = get_company("uk", "Acme Backend Ltd")
    assert reloaded is not None
    match = next(j for j in reloaded["matching_jobs"] if j["url"] == jobs[0]["url"])
    assert match["public_slug"]
    return match


def test_sync_assigns_stable_public_slug(seeded_catalog_v2):
    job = _visa_job(seeded_catalog_v2)
    expected = public_job_slug_base("Acme Backend Ltd", job["title"])
    assert job["public_slug"] == expected
    found = get_public_job_by_slug(expected)
    assert found is not None
    assert found["title"] == job["title"]

    company = get_company("uk", "Acme Backend Ltd")
    company["matching_jobs"] = [
        {**j, "title": "Renamed Role"} if j["url"] == job["url"] else j
        for j in company["matching_jobs"]
    ]
    sync_company_board_to_catalog("uk", company)
    again = get_public_job_by_slug(expected)
    assert again is not None
    assert again["public_slug"] == expected


def test_slug_collision_appends_id(seeded_catalog_v2):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"] = [
        {
            "title": "Shared Title",
            "url": "https://boards.greenhouse.io/acmebackend/jobs/111?gh_jid=111",
            "fetched": "2025-06-01",
            "last_seen": "2025-06-01",
            "visa_sponsorship": True,
        },
        {
            "title": "Shared Title",
            "url": "https://boards.greenhouse.io/acmebackend/jobs/222?gh_jid=222",
            "fetched": "2025-06-01",
            "last_seen": "2025-06-01",
            "visa_sponsorship": True,
        },
    ]
    sync_company_board_to_catalog("uk", company)
    reloaded = get_company("uk", "Acme Backend Ltd")
    slugs = sorted(j["public_slug"] for j in reloaded["matching_jobs"])
    base = public_job_slug_base("Acme Backend Ltd", "Shared Title")
    assert slugs[0] == base
    assert slugs[1].startswith(f"{base}-")


def test_merge_persists_closed_at(seeded_catalog_v2):
    job = _visa_job(seeded_catalog_v2)
    company = get_company("uk", "Acme Backend Ltd")
    other = next(j for j in company["matching_jobs"] if j["url"] != job["url"])
    merge_and_save_jobs(
        "uk",
        "Acme Backend Ltd",
        [{"title": other["title"], "url": other["url"]}],
    )
    closed = get_public_job_by_slug(job["public_slug"])
    assert closed is not None
    assert closed["closed_at"]
    merge_and_save_jobs(
        "uk",
        "Acme Backend Ltd",
        [{"title": job["title"], "url": job["url"], "visa_sponsorship": True}],
    )
    reopened = get_public_job_by_slug(job["public_slug"])
    assert reopened is not None
    assert reopened["closed_at"] == ""


def test_job_posting_json_ld_uses_kuchup_hiring_org(seeded_catalog_v2):
    job = _visa_job(seeded_catalog_v2)
    found = get_public_job_by_slug(job["public_slug"])
    assert found is not None
    payload = job_posting_json_ld(found)
    assert payload["@type"] == "JobPosting"
    assert payload["hiringOrganization"]["name"] == "Kuchup"
    assert payload["title"].endswith("(Visa Sponsorship)")
    assert "Acme Backend Ltd" in payload["title"]
    assert payload["jobLocation"]["address"]["addressCountry"] == "GB"
    assert payload["jobLocation"]["address"]["addressLocality"]
    assert payload["employmentType"] == "FULL_TIME"
    assert payload["applyUrl"] == payload["url"]
    assert "Kuchup" in payload["description"]
    json.dumps(payload)


def test_job_location_label_includes_city_and_country(seeded_catalog_v2):
    from relocation_jobs.catalog.service import job_location_label

    job = _visa_job(seeded_catalog_v2)
    found = get_public_job_by_slug(job["public_slug"])
    assert found is not None
    assert job_location_label(found) == "London, United Kingdom"
