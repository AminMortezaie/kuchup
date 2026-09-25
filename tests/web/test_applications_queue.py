from __future__ import annotations

from relocation_jobs.mcp import service as mcp_service
from relocation_jobs.panel.application_queue import (
    DEFAULT_APPLICATIONS_PAGE_SIZE,
    MAX_APPLICATIONS_PAGE_SIZE,
    count_application_states,
    list_application_queue_positions,
    list_applied_positions,
)
from relocation_jobs.positions.queue import (
    is_active_application_queue_row,
    is_active_applied_row,
    is_rejected_application_row,
)
from tests.helpers.seed import append_matching_jobs


def _first_job(client, country="uk"):
    board = client.get(f"/api/board?country={country}").get_json()
    co = board["companies"][0]
    job = co["jobs"][0]
    return co["name"], job


def _ensure_jobs(company: str, needed: int) -> list[dict]:
    from relocation_jobs.catalog.repo import get_company

    existing = list((get_company("uk", company) or {}).get("matching_jobs") or [])
    if len(existing) >= needed:
        return existing[:needed]
    extra = [
        {
            "title": f"Role {i}",
            "url": f"https://boards.greenhouse.io/acme/jobs/{9000 + i}",
            "visa_sponsorship": True,
        }
        for i in range(len(existing), needed)
    ]
    return append_matching_jobs("uk", company, extra)


def test_is_active_application_queue_row_excludes_applied():
    assert is_active_application_queue_row({"looking_to_apply": 1, "applied": 0})
    assert is_active_application_queue_row({"pinned": 1, "applied": 0})
    assert not is_active_application_queue_row({"pinned": 1, "applied": 1})
    assert not is_active_application_queue_row({"looking_to_apply": 1, "applied": 1})
    assert not is_active_application_queue_row({"pinned": 0, "looking_to_apply": 0})
    assert not is_active_application_queue_row({"pinned": 1, "looking_to_apply": 1, "not_for_me": 1})
    assert not is_active_application_queue_row({"looking_to_apply": 1, "applied": 0, "rejected": 1})


def test_applied_and_rejected_predicates_are_exclusive():
    active = {"applied": 1, "rejected": 0, "not_for_me": 0}
    rejected = {"applied": 1, "rejected": 1, "not_for_me": 0}
    rejected_without_applied = {"applied": 0, "rejected": 1, "not_for_me": 0}
    hidden = {"applied": 1, "rejected": 1, "not_for_me": 1}
    assert is_active_applied_row(active)
    assert not is_rejected_application_row(active)
    assert is_rejected_application_row(rejected)
    assert is_rejected_application_row(rejected_without_applied)
    assert not is_active_applied_row(rejected)
    assert not is_active_applied_row(hidden)
    assert not is_rejected_application_row(hidden)


def test_queue_api_lists_looking_to_apply_position(
    v2_auth_client, seeded_catalog_v2,
):
    company, job = _first_job(v2_auth_client)
    url = job["url"]
    v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": url, "looking_to_apply": True},
    )
    again = v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": url, "looking_to_apply": True},
    )
    assert again.status_code == 200

    payload = v2_auth_client.get("/api/applications/queue").get_json()
    assert "meta" in payload
    assert payload["meta"]["page"] == 1
    assert payload["meta"]["page_size"] <= MAX_APPLICATIONS_PAGE_SIZE
    urls = [item["url"] for item in payload["jobs"]]
    assert urls.count(url) == 1
    item = next(j for j in payload["jobs"] if j["url"] == url)
    assert item["company"] == company
    assert item["looking_to_apply"] is True
    assert item["applied"] is False
    assert "title" in item


def test_queue_sorted_by_looking_to_apply_date_then_pinned_at(
    v2_auth_client, seeded_catalog_v2,
):
    from relocation_jobs.core.db import db_transaction, _normalize_url

    company, _ = _first_job(v2_auth_client)
    older, newer = _ensure_jobs(company, 2)[:2]
    for job in (older, newer):
        assert v2_auth_client.post(
            "/api/jobs/pin",
            json={"country": "uk", "company": company, "url": job["url"], "pinned": True},
        ).status_code == 200

    older_url = _normalize_url(older["url"])
    newer_url = _normalize_url(newer["url"])
    with db_transaction() as conn:
        conn.execute(
            """
            UPDATE job_tracking
            SET looking_to_apply_date = %s, pinned_at = %s
            WHERE country = %s AND company_name = %s AND job_url = %s
            """,
            ("2026-01-01", "2026-01-01T12:00:00+00:00", "uk", company, older_url),
        )
        conn.execute(
            """
            UPDATE job_tracking
            SET looking_to_apply_date = %s, pinned_at = %s
            WHERE country = %s AND company_name = %s AND job_url = %s
            """,
            ("2026-09-20", "2026-09-20T12:00:00+00:00", "uk", company, newer_url),
        )

    queue = v2_auth_client.get("/api/applications/queue").get_json()
    urls = [j["url"] for j in queue["jobs"] if j["url"] in {older["url"], newer["url"]}]
    assert urls == [newer["url"], older["url"]]


def test_queue_api_includes_pinned_only_and_excludes_after_apply(
    v2_auth_client, seeded_catalog_v2,
):
    company, job = _first_job(v2_auth_client)
    url = job["url"]
    v2_auth_client.post(
        "/api/jobs/pin",
        json={"country": "uk", "company": company, "url": url, "pinned": True},
    )
    queued = v2_auth_client.get("/api/applications/queue").get_json()
    assert any(j["url"] == url for j in queued["jobs"])

    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": url, "applied": True},
    )
    after = v2_auth_client.get("/api/applications/queue").get_json()
    assert all(j["url"] != url for j in after["jobs"])

    applied = v2_auth_client.get("/api/applications/applied").get_json()
    match = next(j for j in applied["jobs"] if j["url"] == url)
    assert match["applied"] is True
    assert match["looking_to_apply"] is False
    assert match["rejected"] is False


def test_apply_from_board_updates_persisted_queue_and_mcp(
    v2_auth_client, seeded_catalog_v2, mcp_documents,
):
    company, job = _first_job(v2_auth_client)
    url = job["url"]
    v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": url, "looking_to_apply": True},
    )
    v2_auth_client.post(
        "/api/jobs/pin",
        json={"country": "uk", "company": company, "url": url, "pinned": True},
    )

    before = mcp_service.list_application_queue(user_id=1, country="uk")
    assert any(item.url == url for item in before)
    ctx_before = mcp_service.get_job_context("uk", company, url, user_id=1)
    assert ctx_before.in_application_queue is True

    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": url, "applied": True},
    )

    positions = list_application_queue_positions(1, country="uk")
    assert all(p["url"] != url for p in positions["jobs"])
    assert any(p["url"] == url for p in list_applied_positions(1, country="uk")["jobs"])

    after = mcp_service.list_application_queue(user_id=1, country="uk")
    assert all(item.url != url for item in after)
    ctx_after = mcp_service.get_job_context("uk", company, url, user_id=1)
    assert ctx_after.applied is True
    assert ctx_after.in_application_queue is False
    assert ctx_after.looking_to_apply is False


def test_counts_separate_apply_applied_rejected(
    v2_auth_client, seeded_catalog_v2,
):
    company, _ = _first_job(v2_auth_client)
    jobs = _ensure_jobs(company, 3)
    j1, j2, j3 = jobs[0], jobs[1], jobs[2]

    v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": j1["url"], "looking_to_apply": True},
    )
    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": j2["url"], "applied": True},
    )
    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": j3["url"], "applied": True},
    )
    v2_auth_client.post(
        "/api/jobs/rejected",
        json={"country": "uk", "company": company, "url": j3["url"], "rejected": True},
    )

    counts = v2_auth_client.get("/api/applications/counts").get_json()
    assert set(counts) == {"apply", "applied", "rejected"}
    assert counts["apply"] >= 1
    assert counts["applied"] >= 1
    assert counts["rejected"] >= 1
    assert "jobs" not in counts

    domain = count_application_states(1, country="uk")
    assert domain["apply"] == counts["apply"]
    assert domain["applied"] == counts["applied"]
    assert domain["rejected"] == counts["rejected"]

    applied = v2_auth_client.get("/api/applications/applied").get_json()
    rejected = v2_auth_client.get("/api/applications/rejected").get_json()
    assert any(j["url"] == j2["url"] for j in applied["jobs"])
    assert all(j["url"] != j3["url"] for j in applied["jobs"])
    assert any(j["url"] == j3["url"] for j in rejected["jobs"])
    assert all(j.get("rejected") for j in rejected["jobs"])


def test_list_endpoints_are_state_separated(
    v2_auth_client, seeded_catalog_v2,
):
    company, _ = _first_job(v2_auth_client)
    jobs = _ensure_jobs(company, 3)
    j1, j2, j3 = jobs[0], jobs[1], jobs[2]
    v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": j1["url"], "looking_to_apply": True},
    )
    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": j2["url"], "applied": True},
    )
    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": j3["url"], "applied": True},
    )
    v2_auth_client.post(
        "/api/jobs/rejected",
        json={"country": "uk", "company": company, "url": j3["url"], "rejected": True},
    )

    queue = v2_auth_client.get("/api/applications/queue").get_json()
    applied = v2_auth_client.get("/api/applications/applied").get_json()
    rejected = v2_auth_client.get("/api/applications/rejected").get_json()

    assert any(j["url"] == j1["url"] for j in queue["jobs"])
    assert all(not j.get("applied") for j in queue["jobs"])
    assert any(j["url"] == j2["url"] for j in applied["jobs"])
    assert all(j.get("applied") and not j.get("rejected") for j in applied["jobs"])
    assert any(j["url"] == j3["url"] for j in rejected["jobs"])
    assert all(j.get("applied") and j.get("rejected") for j in rejected["jobs"])


def test_applications_pagination_caps_page_size_and_pages(
    v2_auth_client, seeded_catalog_v2,
):
    company, _ = _first_job(v2_auth_client)
    needed = DEFAULT_APPLICATIONS_PAGE_SIZE + 3
    jobs = _ensure_jobs(company, needed)
    for job in jobs:
        resp = v2_auth_client.post(
            "/api/jobs/looking-to-apply",
            json={
                "country": "uk",
                "company": company,
                "url": job["url"],
                "looking_to_apply": True,
            },
        )
        assert resp.status_code == 200

    oversized = v2_auth_client.get(
        f"/api/applications/queue?page=1&page_size={MAX_APPLICATIONS_PAGE_SIZE + 50}",
    ).get_json()
    assert oversized["meta"]["page_size"] == MAX_APPLICATIONS_PAGE_SIZE
    assert len(oversized["jobs"]) <= MAX_APPLICATIONS_PAGE_SIZE
    assert oversized["meta"]["total"] >= needed
    assert oversized["meta"]["has_more"] is True

    page1 = v2_auth_client.get(
        f"/api/applications/queue?page=1&page_size={DEFAULT_APPLICATIONS_PAGE_SIZE}",
    ).get_json()
    page2 = v2_auth_client.get(
        f"/api/applications/queue?page=2&page_size={DEFAULT_APPLICATIONS_PAGE_SIZE}",
    ).get_json()
    urls1 = [j["url"] for j in page1["jobs"]]
    urls2 = [j["url"] for j in page2["jobs"]]
    assert len(urls1) == DEFAULT_APPLICATIONS_PAGE_SIZE
    assert urls2
    assert not set(urls1) & set(urls2)


def test_state_transition_apply_to_applied_to_rejected(
    v2_auth_client, seeded_catalog_v2,
):
    company, job = _first_job(v2_auth_client)
    url = job["url"]
    v2_auth_client.post(
        "/api/jobs/looking-to-apply",
        json={"country": "uk", "company": company, "url": url, "looking_to_apply": True},
    )
    before = v2_auth_client.get("/api/applications/counts").get_json()

    v2_auth_client.post(
        "/api/jobs/applied",
        json={"country": "uk", "company": company, "url": url, "applied": True},
    )
    mid = v2_auth_client.get("/api/applications/counts").get_json()
    assert mid["apply"] == before["apply"] - 1
    assert mid["applied"] == before["applied"] + 1
    assert mid["rejected"] == before["rejected"]
    assert all(
        j["url"] != url
        for j in v2_auth_client.get("/api/applications/queue").get_json()["jobs"]
    )
    assert any(
        j["url"] == url
        for j in v2_auth_client.get("/api/applications/applied").get_json()["jobs"]
    )

    v2_auth_client.post(
        "/api/jobs/rejected",
        json={"country": "uk", "company": company, "url": url, "rejected": True},
    )
    after = v2_auth_client.get("/api/applications/counts").get_json()
    assert after["applied"] == mid["applied"] - 1
    assert after["rejected"] == mid["rejected"] + 1
    assert all(
        j["url"] != url
        for j in v2_auth_client.get("/api/applications/applied").get_json()["jobs"]
    )
    assert any(
        j["url"] == url
        for j in v2_auth_client.get("/api/applications/rejected").get_json()["jobs"]
    )


def test_applications_page_route(v2_auth_client):
    resp = v2_auth_client.get("/applications")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Applications" in body
    assert "position-card" in body
    assert "applications.js" in body
    assert 'data-applications-tab="rejected"' in body
    assert "/api/applications/counts" not in body


def test_applications_js_lazy_loads_per_tab():
    from pathlib import Path

    src = Path("relocation_jobs/static/js/applications.js").read_text()
    assert 'api("/api/applications/counts")' in src
    assert "LIST_PATH" in src
    assert "/api/applications/rejected" in src
    assert "Promise.all([loadQueue(), loadApplied()])" not in src
    assert "loadCounts" in src
    assert "beginScreenLoad" in src
    assert 'setStatus("Loading' not in src
    assert 'setStatus("Updating' not in src
    assert "PAGE_SIZE = 20" in src
    assert "loadTab(activeTab" in src
    assert "applications-pagination-root" in Path("relocation_jobs/static/applications.html").read_text()
    assert "applications-page-body" in Path("relocation_jobs/static/applications.html").read_text()
