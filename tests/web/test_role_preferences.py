from __future__ import annotations

import pytest

from relocation_jobs.broadcast import repo as broadcast_repo
from relocation_jobs.catalog.repo import (
    get_company,
    list_active_public_jobs,
    list_jobs_for_company_keys,
    sync_company_board_to_catalog,
)
from relocation_jobs.core.ats_constants import EXCLUDE_KEYWORDS, INCLUDE_KEYWORDS
from relocation_jobs.core.db import db_read, db_transaction
from relocation_jobs.roles.service import (
    clear_keyword_cache,
    default_keyword_lists,
    job_is_default_match,
)
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


def test_seeded_tags_match_static_rules(db):
    clear_keyword_cache()
    includes, excludes = default_keyword_lists()
    assert includes == list(INCLUDE_KEYWORDS)
    assert excludes == list(EXCLUDE_KEYWORDS)
    for title in (
        "Senior Backend Engineer",
        "Engineering Manager",
        "Staff Software Engineer",
        "Chief Technology Officer",
        "Software Engineer (Internal Tools & HR Automation)",
    ):
        assert is_relevant(title, include=includes, exclude=excludes) is is_relevant(title)


def test_nondefault_role_stored_without_description_or_public_page(db, seeded_catalog_v2):
    _store_engineering_manager()
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


def test_non_admin_cannot_edit_tags(client, db):
    user = create_user("roletag", email="roletag@example.com", google_sub="sub-role-tag")
    _login(client, user)
    resp = client.post(
        "/api/admin/role-filter-tags",
        json={"keyword": "zzz-widget-keeper", "kind": "exclude"},
    )
    assert resp.status_code == 403


def test_admin_can_add_tag(v2_auth_client, db):
    clear_keyword_cache()
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
        clear_keyword_cache()


def test_backlog_doc_mentions_propagator_followup(db):
    with db_read() as conn:
        rows = conn.execute(
            """
            SELECT title, body FROM team_docs
            WHERE folder = 'tech'
              AND (
                LOWER(title) LIKE '%backlog%'
                OR LOWER(slug) LIKE '%backlog%'
                OR body LIKE %s
              )
            """,
            ("%per-user role keyword preferences%",),
        ).fetchall()
    assert rows
    assert any("per-user role keyword preferences" in (row["body"] or "") for row in rows)
