"""End-to-end checks for admin panel cleanup (API + static shell)."""

from __future__ import annotations

from pathlib import Path

from relocation_jobs.core.paths import STATIC_DIR
from relocation_jobs.users.repo import create_user


def test_panel_hides_admin_nav_for_non_admins():
    html = (Path(STATIC_DIR) / "index.html").read_text(encoding="utf-8")
    css = (Path(STATIC_DIR) / "styles.css").read_text(encoding="utf-8")
    auth_js = (Path(STATIC_DIR) / "js" / "auth.js").read_text(encoding="utf-8")
    assert 'id="adminPanelBtn" hidden' in html
    assert 'id="adminLink" hidden' in html
    assert ".header-secondary-btn[hidden]" in css
    assert ".user-dropdown-admin[hidden]" in css
    assert "setAdminNavVisible(Boolean(user.is_admin))" in auth_js
    assert "setAdminNavVisible(false)" in auth_js


def test_auth_status_is_admin_false_for_regular_user(client, db):
    user = create_user(
        "regular-panel",
        email="regular-panel@example.com",
        google_sub="sub-regular-panel",
    )
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True
    body = client.get("/api/auth/status").get_json()
    assert body["authenticated"] is True
    assert body["user"]["is_admin"] is False


def test_admin_page_serves_cleanup_layout(v2_auth_client):
    resp = v2_auth_client.get("/admin")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="adminWorkerSection"' in html
    assert 'id="adminPanelStats"' in html
    admin_js = (Path(STATIC_DIR) / "js" / "admin.js").read_text(encoding="utf-8")
    assert "./admin-worker.js" in admin_js
    assert 'id="adminOverview"' not in html
    assert "admin-scrape.js" not in html


def test_admin_js_loads_dashboard_once():
    admin_js = (Path(STATIC_DIR) / "js" / "admin.js").read_text(encoding="utf-8")
    assert admin_js.count("/api/admin/dashboard") >= 1
    assert "/api/admin/panel-stats" in admin_js
    assert "/api/admin/catalog" in admin_js
    assert "/api/admin/users" in admin_js
    assert "/api/admin/fetch-runs" in admin_js
    assert "/api/admin/recent-jobs" in admin_js
    assert "/api/admin/config" in admin_js
    assert "renderOverview" not in admin_js
    assert "adminOverview" not in admin_js


def test_admin_dashboard_worker_last_country_run(v2_auth_client, seeded_catalog_v2, db):
    from relocation_jobs.users.repo import get_user_by_username
    from relocation_jobs.fetch import repo as fetch_repo

    del seeded_catalog_v2, db
    user_id = get_user_by_username("admin")["id"]
    run_id = int(fetch_repo.create_fetch_run(
        user_id=user_id,
        country="uk",
        company_name=None,
        file_name="uk.json",
        concurrency=2,
        started_at="2025-07-01T10:00:00+00:00",
    )["id"])
    fetch_repo.finalize_fetch_run(
        run_id,
        finished_at="2025-07-01T10:30:00+00:00",
        exit_code=0,
        new_jobs=7,
        companies_done=3,
        companies_total=3,
        result_line="Done",
    )
    company_run_id = int(fetch_repo.create_fetch_run(
        user_id=user_id,
        country="uk",
        company_name="Acme Backend Ltd",
        file_name="uk.json",
        concurrency=1,
        started_at="2025-07-02T11:00:00+00:00",
    )["id"])
    fetch_repo.finalize_fetch_run(
        company_run_id,
        finished_at="2025-07-02T11:05:00+00:00",
        exit_code=0,
        new_jobs=99,
    )

    payload = v2_auth_client.get("/api/admin/dashboard?limit=15&timezone=UTC").get_json()
    worker = payload["worker"]
    assert worker["fetch"]["running"] is False
    assert worker["panel_scrape_enabled"] is False
    assert worker["panel_company_fetch_enabled"] is False
    last = worker["last_country_run"]
    assert last is not None
    assert last["scope"] == "country"
    assert last["country"] == "uk"
    assert last["new_jobs"] == 7
    assert last["company_name"] in (None, "")


def test_admin_dashboard_panel_stats_matches_standalone(v2_auth_client, seeded_catalog_v2):
    dashboard = v2_auth_client.get("/api/admin/dashboard?timezone=UTC").get_json()
    standalone = v2_auth_client.get("/api/admin/panel-stats?timezone=UTC").get_json()
    assert dashboard["panel_stats"] is None
    for key in (
        "total_jobs",
        "companies_with_jobs",
        "positions_applied",
        "positions_not_for_me",
        "positions_rejected",
        "latest_fetch_new_jobs",
        "visa_sponsored",
    ):
        assert key in standalone


def test_admin_dashboard_runs_respect_limit(v2_auth_client, seeded_catalog_v2, db):
    from relocation_jobs.users.repo import get_user_by_username
    from relocation_jobs.fetch import repo as fetch_repo

    del seeded_catalog_v2
    user_id = get_user_by_username("admin")["id"]
    for idx in range(20):
        run_id = int(fetch_repo.create_fetch_run(
            user_id=user_id,
            country="uk",
            company_name=None,
            file_name="uk.json",
            concurrency=1,
            started_at=f"2025-06-{idx + 1:02d}T12:00:00+00:00",
        )["id"])
        fetch_repo.finalize_fetch_run(
            run_id,
            finished_at=f"2025-06-{idx + 1:02d}T12:05:00+00:00",
            exit_code=0,
            new_jobs=1,
        )

    payload = v2_auth_client.get("/api/admin/fetch-runs?limit=15").get_json()
    assert len(payload["runs"]) == 15


def test_admin_dashboard_catalog_has_country_meta(v2_auth_client, seeded_catalog_v2):
    del seeded_catalog_v2
    catalog = v2_auth_client.get("/api/admin/catalog").get_json()
    assert catalog["has_data"] is True
    assert catalog["countries"]
    assert "country_meta" in catalog
    assert "fetch_problem_companies" in catalog
    uk = next(row for row in catalog["countries"] if row["country"] == "uk")
    assert "jobs" in uk
    assert "companies" in uk
