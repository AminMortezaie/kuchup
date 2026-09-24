from __future__ import annotations

import pytest

from relocation_jobs.broadcast import repo as broadcast_repo
from relocation_jobs.catalog.repo import (
    get_company,
    list_active_public_jobs,
    list_jobs_for_company_keys,
    sync_company_board_to_catalog,
)
from relocation_jobs.core.db import db_read, db_transaction
from relocation_jobs.roles.match import job_is_default_match
from relocation_jobs.roles.service import annotate_listings, default_keyword_lists
from relocation_jobs.scrape.company import process_company
from relocation_jobs.scrape.relevance import is_relevant
from relocation_jobs.users.repo import create_user
from tests.helpers.seed import seed_free_assignments

_EM_URL = "https://boards.greenhouse.io/acmebackend/jobs/777?gh_jid=777"


def _login(client, user: dict) -> None:
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True


def _store_engineering_manager() -> None:
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"] = list(company.get("matching_jobs") or []) + [{
        "title": "Engineering Manager",
        "url": _EM_URL,
        "location": "London",
        "description_text": "a long job description that must not be stored",
        "visa_sponsorship": True,
        "matches_default_filter": 0,
    }]
    sync_company_board_to_catalog("uk", company)


def _board_titles(client) -> list[str]:
    payload = client.get("/api/board?country=uk").get_json()
    return [
        job["title"]
        for company in payload["companies"]
        for job in company.get("jobs") or []
    ]


def test_seeded_tags_drive_title_matching(db):
    includes, excludes = default_keyword_lists()
    assert "backend" in includes
    assert "engineering manager" in excludes
    for title, expected in (
        ("Senior Backend Engineer", True),
        ("Engineering Manager", False),
        ("Staff Software Engineer", False),
        ("Chief Technology Officer", False),
        ("Software Engineer (Internal Tools & HR Automation)", True),
    ):
        assert is_relevant(title, include=includes, exclude=excludes) is expected


def test_nondefault_role_stored_without_description_or_public_page(db, seeded_catalog_v2):
    includes, excludes = default_keyword_lists()
    listed = annotate_listings([{
        "title": "Engineering Manager",
        "url": _EM_URL,
        "location": "London",
        "description_text": "a long job description that must not be stored",
        "visa_sponsorship": True,
    }], includes, excludes)
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"] = list(company.get("matching_jobs") or []) + listed
    sync_company_board_to_catalog("uk", company)
    company = get_company("uk", "Acme Backend Ltd")
    stored = next(job for job in company["matching_jobs"] if job["url"] == _EM_URL)
    assert job_is_default_match(stored) is False
    assert not (stored.get("description_text") or "").strip()
    assert stored.get("visa_sponsorship") is None
    assert not (stored.get("public_slug") or "").strip()
    assert stored.get("location") == "London"
    keys = list_jobs_for_company_keys([("uk", "Acme Backend Ltd")])
    titles = [job["title"] for job in keys[("uk", "acme backend ltd")]]
    assert "Engineering Manager" not in titles
    assert all("Engineering Manager" not in (job.get("title") or "") for job in list_active_public_jobs())


@pytest.mark.asyncio
async def test_scrape_skips_description_fetch_for_nondefault(db, seeded_catalog_v2):
    enriched: list[str] = []

    async def fetch_board(_client, _company, **kwargs):
        return [
            {
                "title": "Backend Engineer",
                "url": "https://boards.greenhouse.io/acmebackend/jobs/555?gh_jid=555",
                "location": "London",
            },
            {
                "title": "Engineering Manager",
                "url": _EM_URL,
                "location": "Berlin",
                "description_text": "do not keep",
            },
        ]

    async def enrich(_client, jobs, _company, **kwargs):
        enriched.extend((job.get("title") or "") for job in jobs)
        for job in jobs:
            job["description_text"] = "fetched"
            job["visa_sponsorship"] = True
        return jobs

    company = get_company("uk", "Acme Backend Ltd")
    _line, new_count = await process_company(
        None,
        company,
        1,
        1,
        fetch_board=fetch_board,
        enrich_board=enrich,
        catalog_country="uk",
        sync_board=lambda: sync_company_board_to_catalog("uk", company),
    )
    assert "Engineering Manager" not in enriched
    assert "Backend Engineer" in enriched
    assert new_count == 1
    stored = get_company("uk", "Acme Backend Ltd")
    manager = next(job for job in stored["matching_jobs"] if "777" in job["url"])
    assert job_is_default_match(manager) is False
    assert not (manager.get("description_text") or "").strip()
    backend = next(job for job in stored["matching_jobs"] if "555" in job["url"])
    assert (backend.get("description_text") or "") == "fetched"


def test_default_user_board_hides_nondefault_until_tag_off(client, db, seeded_catalog_v2):
    _store_engineering_manager()
    user = create_user("roleprefs", email="roleprefs@example.com", google_sub="sub-role-prefs")
    user_id = int(user["id"])
    seed_free_assignments(user_id, ["uk"])
    _login(client, user)
    before = broadcast_repo.list_assignments(user_id)
    with db_read() as conn:
        before_opps = int(conn.execute(
            "SELECT COUNT(*) AS n FROM user_opportunities WHERE user_id = %s",
            (user_id,),
        ).fetchone()["n"])
    assert before_opps >= 1
    assert "Engineering Manager" not in _board_titles(client)
    tags = client.get("/api/role-preferences").get_json()["tags"]
    include = next(item for item in tags if item["kind"] == "include")
    assert include["enabled"] is True
    turned_off = client.put(
        f"/api/role-preferences/{include['id']}",
        json={"enabled": False},
    )
    assert turned_off.status_code == 200
    assert turned_off.get_json()["tag"]["enabled"] is False
    tag = next(item for item in tags if item["keyword"] == "engineering manager" and item["kind"] == "exclude")
    assert tag["enabled"] is True
    saved = client.put(
        f"/api/role-preferences/{tag['id']}",
        json={"enabled": False},
    )
    assert saved.status_code == 200
    assert saved.get_json()["tag"]["enabled"] is False
    titles = _board_titles(client)
    assert "Engineering Manager" in titles
    after = broadcast_repo.list_assignments(user_id)
    assert [(row.job_key, row.job_url) for row in before] == [(row.job_key, row.job_url) for row in after]
    with db_read() as conn:
        after_opps = int(conn.execute(
            "SELECT COUNT(*) AS n FROM user_opportunities WHERE user_id = %s",
            (user_id,),
        ).fetchone()["n"])
    assert after_opps == before_opps


def test_user_can_add_personal_match_tag(client, db, seeded_catalog_v2):
    _store_engineering_manager()
    user = create_user("rolemine", email="rolemine@example.com", google_sub="sub-role-mine")
    user_id = int(user["id"])
    seed_free_assignments(user_id, ["uk"])
    _login(client, user)
    assert "Engineering Manager" not in _board_titles(client)
    added = client.post(
        "/api/role-preferences/mine",
        json={"keyword": "engineering manager", "kind": "include"},
    )
    assert added.status_code == 201
    assert added.get_json()["tag"]["personal"] is True
    assert "Engineering Manager" in _board_titles(client)
    prefs = client.get("/api/role-preferences").get_json()
    mine_id = prefs["mine"][0]["id"]
    deleted = client.delete(f"/api/role-preferences/mine/{mine_id}")
    assert deleted.status_code == 200
    assert "Engineering Manager" not in _board_titles(client)


def test_personal_hide_matches_separator_siblings(client, db, seeded_catalog_v2):
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"] = list(company.get("matching_jobs") or []) + [{
        "title": "Full Stack Engineer",
        "url": "https://boards.greenhouse.io/acmebackend/jobs/888?gh_jid=888",
        "location": "London",
        "description_text": "kept for default match",
        "visa_sponsorship": True,
        "matches_default_filter": 1,
    }]
    sync_company_board_to_catalog("uk", company)
    user = create_user("rolehide", email="rolehide@example.com", google_sub="sub-role-hide")
    user_id = int(user["id"])
    seed_free_assignments(user_id, ["uk"])
    _login(client, user)
    assert "Full Stack Engineer" in _board_titles(client)
    added = client.post(
        "/api/role-preferences/mine",
        json={"keyword": "fullstack", "kind": "exclude"},
    )
    assert added.status_code == 201
    assert "Full Stack Engineer" not in _board_titles(client)


def test_non_admin_cannot_edit_tags(client, db):
    user = create_user("roletag", email="roletag@example.com", google_sub="sub-role-tag")
    _login(client, user)
    resp = client.post(
        "/api/admin/role-filter-tags",
        json={"keyword": "zzz-widget-keeper", "kind": "exclude"},
    )
    assert resp.status_code == 403


def test_admin_can_add_tag(v2_auth_client, db):
    tag_id = None
    try:
        resp = v2_auth_client.post(
            "/api/admin/role-filter-tags",
            json={"keyword": "zzz-widget-keeper", "kind": "exclude"},
        )
        assert resp.status_code == 201
        tag = resp.get_json()["tag"]
        tag_id = tag["id"]
        assert tag["keyword"] == "zzz-widget-keeper"
        edited = v2_auth_client.patch(
            f"/api/admin/role-filter-tags/{tag_id}",
            json={"keyword": "zzz-widget-keeper", "kind": "include"},
        )
        assert edited.status_code == 200
        assert edited.get_json()["tag"]["kind"] == "include"
    finally:
        if tag_id is not None:
            with db_transaction() as conn:
                conn.execute("DELETE FROM role_filter_tags WHERE id = %s", (tag_id,))


@pytest.mark.asyncio
async def test_nondefault_keeps_fetched_then_closes(db, seeded_catalog_v2):
    backend = {
        "title": "Backend Engineer",
        "url": "https://boards.greenhouse.io/acmebackend/jobs/555?gh_jid=555",
        "location": "London",
    }
    software = {
        "title": "Software Engineer",
        "url": "https://boards.greenhouse.io/acmebackend/jobs/556?gh_jid=556",
        "location": "London",
    }
    manager = {
        "title": "Engineering Manager",
        "url": _EM_URL,
        "location": "Berlin",
    }

    async def fetch_all(_client, _company, **kwargs):
        return [backend, software, manager]

    async def fetch_backend(_client, _company, **kwargs):
        return [backend]

    async def enrich(_client, jobs, _company, **kwargs):
        return jobs

    async def scrape(fetch_board) -> None:
        company = get_company("uk", "Acme Backend Ltd")
        assert company is not None
        await process_company(
            None,
            company,
            1,
            1,
            fetch_board=fetch_board,
            enrich_board=enrich,
            catalog_country="uk",
            sync_board=lambda: sync_company_board_to_catalog("uk", company),
        )

    await scrape(fetch_all)
    first = get_company("uk", "Acme Backend Ltd")
    stored = next(job for job in first["matching_jobs"] if "777" in job["url"])
    kept = next(job for job in first["matching_jobs"] if "556" in job["url"])
    assert job_is_default_match(kept) is True
    fetched = stored["fetched"]
    assert fetched
    await scrape(fetch_all)
    second = get_company("uk", "Acme Backend Ltd")
    again = next(job for job in second["matching_jobs"] if "777" in job["url"])
    assert again["fetched"] == fetched
    assert not (again.get("closed_at") or "").strip()
    await scrape(fetch_backend)
    third = get_company("uk", "Acme Backend Ltd")
    closed_manager = next(job for job in third["matching_jobs"] if "777" in job["url"])
    closed_software = next(job for job in third["matching_jobs"] if "556" in job["url"])
    assert (closed_manager.get("closed_at") or "").strip()
    assert (closed_software.get("closed_at") or "").strip()
    assert closed_manager["fetched"] == fetched
