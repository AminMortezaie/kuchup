from __future__ import annotations

from pathlib import Path

from relocation_jobs.catalog.repo import delete_company, get_company
from relocation_jobs.catalog.schema import _migrate_owned_by_kuchup_v1
from relocation_jobs.core.db import db_transaction
from relocation_jobs.core.migrations import _seed_kuchup_ownership_doc


def _login(client, user) -> None:
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True


def _silence_enrichment(monkeypatch) -> None:
    monkeypatch.setattr(
        "relocation_jobs.companies.service.fetch_relocate_metadata",
        lambda name, country_key=None: {},
    )
    monkeypatch.setattr(
        "relocation_jobs.companies.service.detect_ats_for_company",
        lambda name, url, ats_hint=None: (
            "greenhouse",
            "https://boards.greenhouse.io/example",
        ),
    )


def test_seeded_companies_are_kuchup(db, seeded_catalog_v2):
    del db, seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    assert company["owned_by_kuchup"] is True


def test_migration_tags_existing_companies(db, seeded_catalog_v2):
    del db, seeded_catalog_v2
    assert get_company("uk", "Acme Backend Ltd")["owned_by_kuchup"] is True
    with db_transaction() as conn:
        conn.execute("UPDATE companies SET owned_by_kuchup = 0")
        _migrate_owned_by_kuchup_v1(conn)
    assert get_company("uk", "Acme Backend Ltd")["owned_by_kuchup"] is True


def test_non_admin_blocked_on_kuchup_company(v2_client, test_user, seeded_catalog_v2, monkeypatch):
    del seeded_catalog_v2
    monkeypatch.setenv("PANEL_SCRAPE_ENABLED", "1")
    _login(v2_client, test_user)
    body = {"country": "uk", "company": "Acme Backend Ltd"}
    rename = v2_client.post("/api/companies/name", json={**body, "new_name": "Not Acme"})
    careers = v2_client.post(
        "/api/companies/careers",
        json={**body, "careers_url": "https://example.com/jobs"},
    )
    refresh = v2_client.post("/api/companies/fetch", json=body)
    remove = v2_client.post("/api/companies/remove", json=body)
    for response in (rename, careers, refresh, remove):
        assert response.status_code == 403
        assert response.get_json()["error"] == "Only an admin can change a Kuchup company"
    stored = get_company("uk", "Acme Backend Ltd")
    assert stored is not None
    assert stored["name"] == "Acme Backend Ltd"


def test_admin_can_edit_kuchup_company(v2_auth_client, db, monkeypatch):
    del db
    _silence_enrichment(monkeypatch)
    monkeypatch.setenv("PANEL_SCRAPE_ENABLED", "1")
    started: list[str] = []

    def fake_start(*, user_id, country_key, company_name):
        del user_id, country_key
        started.append(company_name)
        return 77

    monkeypatch.setattr(
        "relocation_jobs.web.routes.companies.start_company_fetch",
        fake_start,
    )
    try:
        created = v2_auth_client.post(
            "/api/companies",
            json={
                "name": "Ownership Admin Co",
                "country": "uk",
                "careers_url": "https://boards.greenhouse.io/ownership-admin",
            },
        )
        assert created.status_code == 200
        assert get_company("uk", "Ownership Admin Co")["owned_by_kuchup"] is True

        renamed = v2_auth_client.post(
            "/api/companies/name",
            json={
                "country": "uk",
                "company": "Ownership Admin Co",
                "new_name": "Ownership Admin Renamed",
            },
        )
        assert renamed.status_code == 200
        careers = v2_auth_client.post(
            "/api/companies/careers",
            json={
                "country": "uk",
                "company": "Ownership Admin Renamed",
                "careers_url": "https://example.com/careers",
            },
        )
        assert careers.status_code == 200
        refresh = v2_auth_client.post(
            "/api/companies/fetch",
            json={"country": "uk", "company": "Ownership Admin Renamed"},
        )
        assert refresh.status_code == 200
        assert started == ["Ownership Admin Renamed"]
        removed = v2_auth_client.post(
            "/api/companies/remove",
            json={"country": "uk", "company": "Ownership Admin Renamed"},
        )
        assert removed.status_code == 200
        assert get_company("uk", "Ownership Admin Renamed") is None
    finally:
        delete_company("uk", "Ownership Admin Co")
        delete_company("uk", "Ownership Admin Renamed")


def test_non_admin_cannot_post_careers_url_on_add(v2_client, test_user, db, monkeypatch):
    del db
    _silence_enrichment(monkeypatch)
    _login(v2_client, test_user)
    denied = v2_client.post(
        "/api/companies",
        json={
            "name": "Ownership User Co",
            "country": "uk",
            "careers_url": "https://example.com/careers",
        },
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "Only an admin can set a careers or ATS URL"
    assert get_company("uk", "Ownership User Co") is None

    ats = v2_client.post(
        "/api/companies",
        json={
            "name": "Ownership User Co",
            "country": "uk",
            "ats": "greenhouse",
        },
    )
    assert ats.status_code == 403
    assert get_company("uk", "Ownership User Co") is None

    try:
        created = v2_client.post(
            "/api/companies",
            json={"name": "Ownership User Co", "country": "uk"},
        )
        assert created.status_code == 200
        stored = get_company("uk", "Ownership User Co")
        assert stored is not None
        assert stored["careers_url"] == ""
        assert stored["owned_by_kuchup"] is False
    finally:
        delete_company("uk", "Ownership User Co")


def test_ownership_doc_seeded_into_admin_docs(v2_auth_client, db):
    del db
    with db_transaction() as conn:
        _seed_kuchup_ownership_doc(conn)
        _seed_kuchup_ownership_doc(conn)
    tree = v2_auth_client.get("/api/admin/team-docs").get_json()
    tech = next(folder for folder in tree["folders"] if folder["slug"] == "tech")
    matches = [doc for doc in tech["docs"] if doc["slug"] == "kuchup-company-ownership"]
    assert len(matches) == 1
    assert matches[0]["title"] == "Kuchup company ownership and edit permissions"
    fetched = v2_auth_client.get(f"/api/admin/team-docs/{matches[0]['id']}").get_json()["doc"]
    assert "owned_by_kuchup" in fetched["body"]
    assert "is_user_admin" in fetched["body"]
    assert "<code>owned_by_kuchup</code>" in fetched["html"]


def test_panel_ui_gates_match_server():
    root = Path(__file__).resolve().parents[2]
    card = (root / "frontend/src/CompanyCard.jsx").read_text(encoding="utf-8")
    board_view = (root / "relocation_jobs/static/js/board-view.js").read_text(encoding="utf-8")
    dialogs = (root / "relocation_jobs/static/js/dialogs.js").read_text(encoding="utf-8")
    html = (root / "relocation_jobs/static/index.html").read_text(encoding="utf-8")
    bundle = (root / "relocation_jobs/static/dist/board.js").read_text(encoding="utf-8")
    assert "kuchupCatalogLocked" in card
    assert "isAdmin: Boolean(state.authState?.user?.is_admin)" in board_view
    assert "syncAddCompanyCatalogFields" in dialogs
    assert 'id="addCompanyUrlField"' in html
    assert "board.js?v=23" in html
    assert "main.js?v=137" in html
    assert "data-kuchup-lock" in bundle
