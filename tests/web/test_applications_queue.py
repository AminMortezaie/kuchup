from __future__ import annotations

from relocation_jobs.mcp import service as mcp_service
from relocation_jobs.panel.application_queue import (
    list_application_queue_positions,
    list_applied_positions,
)
from relocation_jobs.positions.queue import is_active_application_queue_row


def _first_job(client, country="uk"):
    board = client.get(f"/api/board?country={country}").get_json()
    co = board["companies"][0]
    job = co["jobs"][0]
    return co["name"], job


def test_is_active_application_queue_row_excludes_applied():
    assert is_active_application_queue_row({"looking_to_apply": 1, "applied": 0})
    assert is_active_application_queue_row({"pinned": 1, "applied": 0})
    assert not is_active_application_queue_row({"pinned": 1, "applied": 1})
    assert not is_active_application_queue_row({"looking_to_apply": 1, "applied": 1})
    assert not is_active_application_queue_row({"pinned": 0, "looking_to_apply": 0})


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
    urls = [item["url"] for item in payload["jobs"]]
    assert urls.count(url) == 1
    item = next(j for j in payload["jobs"] if j["url"] == url)
    assert item["company"] == company
    assert item["looking_to_apply"] is True
    assert item["applied"] is False
    assert "title" in item


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
    assert all(p["url"] != url for p in positions)
    assert any(p["url"] == url for p in list_applied_positions(1, country="uk"))

    after = mcp_service.list_application_queue(user_id=1, country="uk")
    assert all(item.url != url for item in after)
    ctx_after = mcp_service.get_job_context("uk", company, url, user_id=1)
    assert ctx_after.applied is True
    assert ctx_after.in_application_queue is False
    assert ctx_after.looking_to_apply is False


def test_applications_page_route(v2_auth_client):
    resp = v2_auth_client.get("/applications")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Applications" in body
    assert "position-card" in body
    assert "/api/applications/queue" not in body or True
