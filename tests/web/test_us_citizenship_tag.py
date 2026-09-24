from __future__ import annotations

from pathlib import Path

from relocation_jobs.catalog.citizenship import url_requires_us_citizenship
from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog, upsert_company
from relocation_jobs.catalog.schema import _migrate_citizenship_required_v1
from relocation_jobs.core.db import db_transaction
from relocation_jobs.core.migrations import _seed_us_citizenship_doc
from relocation_jobs.scrape.aggregator_seeds import ensure_aggregator_seeds
from relocation_jobs.scrape.merge import now_iso


GDIT_URL = "https://gdit.wd5.myworkdayjobs.com/en-US/External_Career_Site"


def _login(client, user) -> None:
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True


def _company(name: str, *, careers_url: str, ats_url: str = "", title: str = "Software Developer") -> dict:
    ts = now_iso()
    return {
        "name": name,
        "city": "",
        "size": "",
        "careers_url": careers_url,
        "ats_type": "workday",
        "ats_url": ats_url,
        "matching_jobs": [
            {
                "title": title,
                "url": f"{careers_url.rstrip('/')}/job/{name}",
                "fetched": ts,
                "last_seen": ts,
            }
        ],
        "sources": ["panel"],
        "added": ts,
        "updated": ts,
    }


def _remote_job(client, company: str) -> dict:
    payload = client.get(f"/api/remote/board?country=remote-ok&q={company}").get_json()
    match = next(row for row in payload["companies"] if row["name"] == company)
    return match["jobs"][0]


def test_gdit_workday_host_match():
    job = "https://gdit.wd5.myworkdayjobs.com/en-US/External_Career_Site/job/Software-Developer_RQ229108-1"
    assert url_requires_us_citizenship(job) is True
    assert url_requires_us_citizenship("https://www.gdit.wd1.myworkdayjobs.com/External") is True
    assert url_requires_us_citizenship("https://leidos.wd5.myworkdayjobs.com/External") is False
    assert url_requires_us_citizenship("https://notgdit.wd5.myworkdayjobs.com/External") is False
    assert url_requires_us_citizenship("https://boards.greenhouse.io/gdit") is False


def test_gdit_jobs_are_tagged_and_other_companies_are_not(v2_auth_client, db):
    del db
    ensure_aggregator_seeds()
    upsert_company("remote-ok", _company("GDIT", careers_url=GDIT_URL, title="Software Developer"))
    upsert_company(
        "remote-ok",
        _company("Orbit Remote", careers_url="https://boards.greenhouse.io/orbit", title="Platform Engineer"),
    )

    assert get_company("remote-ok", "GDIT")["citizenship_required"] == "US"
    assert get_company("remote-ok", "Orbit Remote")["citizenship_required"] == ""
    assert _remote_job(v2_auth_client, "GDIT")["citizenship_required"] == "US"
    assert _remote_job(v2_auth_client, "Orbit Remote")["citizenship_required"] == ""

    workspace = v2_auth_client.get("/api/mcp/companies/remote-ok/GDIT/applications").get_json()
    assert workspace["positions"][0]["citizenship_required"] == "US"
    plain = v2_auth_client.get("/api/mcp/companies/remote-ok/Orbit%20Remote/applications").get_json()
    assert plain["positions"][0]["citizenship_required"] == ""


def test_catalog_sync_keeps_citizenship_flag(db):
    del db
    upsert_company(
        "uk",
        _company("Leidos", careers_url="https://boards.greenhouse.io/leidos", ats_url="https://boards.greenhouse.io/leidos"),
    )
    with db_transaction() as conn:
        conn.execute(
            "UPDATE companies SET citizenship_required = %s WHERE lower(name) = lower(%s)",
            ("US", "Leidos"),
        )
    stored = get_company("uk", "Leidos")
    stored["citizenship_required"] = ""
    stored["matching_jobs"][0]["title"] = "Cleared title"
    sync_company_board_to_catalog("uk", stored)
    assert get_company("uk", "Leidos")["citizenship_required"] == "US"
    assert get_company("uk", "Leidos")["matching_jobs"][0]["title"] == "Cleared title"


def test_gdit_sync_refills_empty_flag(db):
    del db
    upsert_company("uk", _company("GDIT", careers_url=GDIT_URL, ats_url=GDIT_URL))
    with db_transaction() as conn:
        conn.execute(
            "UPDATE companies SET citizenship_required = '' WHERE lower(name) = lower(%s)",
            ("GDIT",),
        )
    stored = get_company("uk", "GDIT")
    assert stored["citizenship_required"] == ""
    sync_company_board_to_catalog("uk", stored)
    assert get_company("uk", "GDIT")["citizenship_required"] == "US"


def test_migration_tags_gdit_host_and_is_idempotent(db):
    del db
    upsert_company(
        "uk",
        _company("Plain Co", careers_url="https://boards.greenhouse.io/plain"),
    )
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE companies
            SET careers_url = %s, ats_url = %s, citizenship_required = ''
            WHERE lower(name) = lower(%s)
            """,
            (GDIT_URL, "", "Plain Co"),
        )
        _migrate_citizenship_required_v1(conn)
        _migrate_citizenship_required_v1(conn)
    assert get_company("uk", "Plain Co")["citizenship_required"] == "US"

    upsert_company(
        "uk",
        _company("Still Plain", careers_url="https://boards.greenhouse.io/still-plain"),
    )
    with db_transaction() as conn:
        _migrate_citizenship_required_v1(conn)
    assert get_company("uk", "Still Plain")["citizenship_required"] == ""


def test_citizenship_edit_rejects_non_admins(v2_client, test_user, db):
    del db
    upsert_company(
        "uk",
        _company("Tag Target", careers_url="https://boards.greenhouse.io/tag-target"),
    )
    _login(v2_client, test_user)
    denied = v2_client.post(
        "/api/companies/citizenship",
        json={"country": "uk", "company": "Tag Target", "citizenship_required": "US"},
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "Only an admin can set a citizenship requirement"
    assert get_company("uk", "Tag Target")["citizenship_required"] == ""


def test_admin_can_set_and_clear_citizenship(v2_auth_client, db):
    del db
    upsert_company(
        "uk",
        _company("SAIC", careers_url="https://boards.greenhouse.io/saic", title="Systems Engineer"),
    )
    missing = v2_auth_client.post(
        "/api/companies/citizenship",
        json={"country": "uk", "company": "SAIC", "citizenship_required": "DE"},
    )
    assert missing.status_code == 400
    set_us = v2_auth_client.post(
        "/api/companies/citizenship",
        json={"country": "uk", "company": "SAIC", "citizenship_required": "US"},
    )
    assert set_us.status_code == 200
    assert get_company("uk", "SAIC")["citizenship_required"] == "US"
    board = v2_auth_client.get("/api/board?country=uk&q=SAIC").get_json()
    company = next(row for row in board["companies"] if row["name"] == "SAIC")
    assert company["jobs"][0]["citizenship_required"] == "US"
    cleared = v2_auth_client.post(
        "/api/companies/citizenship",
        json={"country": "uk", "company": "SAIC", "citizenship_required": ""},
    )
    assert cleared.status_code == 200
    assert get_company("uk", "SAIC")["citizenship_required"] == ""


def test_citizenship_doc_seed_is_idempotent(v2_auth_client, db):
    del db
    with db_transaction() as conn:
        _seed_us_citizenship_doc(conn)
        _seed_us_citizenship_doc(conn)
    tree = v2_auth_client.get("/api/admin/team-docs").get_json()
    tech = next(folder for folder in tree["folders"] if folder["slug"] == "tech")
    matches = [doc for doc in tech["docs"] if doc["slug"] == "job-eligibility-us-citizenship"]
    assert len(matches) == 1
    assert matches[0]["title"] == "Job eligibility tags: US Citizenship Required"
    fetched = v2_auth_client.get(f"/api/admin/team-docs/{matches[0]['id']}").get_json()["doc"]
    assert "citizenship_required" in fetched["body"]
    assert "gdit.wd5.myworkdayjobs.com" in fetched["body"]
    page = Path(__file__).resolve().parents[2] / "relocation_jobs/team_docs/pages/job-eligibility-us-citizenship.md"
    assert page.is_file()
