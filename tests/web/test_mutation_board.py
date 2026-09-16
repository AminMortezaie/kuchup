from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.seed import replace_matching_jobs, seed_country

ACME = "Acme Backend Ltd"
BOARD_QS = "include_board=1&country=uk&sort=newest&page=1&page_size=25"


def _acme_job(client):
    board = client.get("/api/board?country=uk").get_json()
    company = next(row for row in board["companies"] if row["name"] == ACME)
    return company, company["jobs"][0]


def _hide(client, job, extra_qs=""):
    qs = BOARD_QS if not extra_qs else extra_qs
    return client.post(
        f"/api/jobs/not-for-me?{qs}",
        json={
            "country": "uk",
            "company": ACME,
            "url": job["url"],
            "not_for_me": True,
            "reason": "not_for_me",
        },
    )


def test_not_for_me_without_include_board_omits_snapshot(v2_auth_client, seeded_catalog_v2):
    _, job = _acme_job(v2_auth_client)
    resp = v2_auth_client.post(
        "/api/jobs/not-for-me",
        json={
            "country": "uk",
            "company": ACME,
            "url": job["url"],
            "not_for_me": True,
            "reason": "not_for_me",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["not_for_me"] is True
    assert "board" not in payload
    assert "user_stats" not in payload


def test_not_for_me_returns_board_matching_get(v2_auth_client, seeded_catalog_v2):
    _, job = _acme_job(v2_auth_client)
    resp = _hide(v2_auth_client, job)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["not_for_me"] is True
    assert "companies" in payload["board"]
    assert "meta" in payload["board"]
    assert "positions_applied" in payload["user_stats"]

    follow = v2_auth_client.get("/api/board?country=uk&sort=newest&page=1&page_size=25")
    assert follow.status_code == 200
    board = follow.get_json()
    assert [row["name"] for row in payload["board"]["companies"]] == [
        row["name"] for row in board["companies"]
    ]
    acme = next(row for row in payload["board"]["companies"] if row["name"] == ACME)
    hidden = next(row for row in acme["not_for_me_jobs"] if row["url"] == job["url"])
    assert hidden["not_for_me"] is True
    assert payload["board"]["meta"]["total_companies"] == board["meta"]["total_companies"]
    assert payload["board"]["meta"]["sort"] == "newest"
    assert payload["user_stats"]["positions_applied"] == board["user_stats"]["positions_applied"]


def test_applied_returns_board_with_hide_applied(v2_auth_client, seeded_catalog_v2):
    company, job = _acme_job(v2_auth_client)
    for open_job in company["jobs"]:
        resp = v2_auth_client.post(
            f"/api/jobs/applied?{BOARD_QS}&hide_applied=1",
            json={
                "country": "uk",
                "company": ACME,
                "url": open_job["url"],
                "applied": True,
            },
        )
        assert resp.status_code == 200
    payload = resp.get_json()
    names = [row["name"] for row in payload["board"]["companies"]]
    assert ACME not in names
    assert payload["board"]["meta"]["total_companies"] == 0
    follow = v2_auth_client.get("/api/board?country=uk&hide_applied=1").get_json()
    assert follow["companies"] == []


@pytest.mark.fresh_db
def test_not_for_me_hide_empty_drops_company_from_mutation_board(v2_auth_client, db):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "country_uk_minimal.json"
    seed_country("uk", fixture)
    replace_matching_jobs("uk", ACME, [
        {"title": "Hidden role", "url": "https://boards.greenhouse.io/acmebackend/jobs/999"},
    ])
    job = {"url": "https://boards.greenhouse.io/acmebackend/jobs/999"}
    resp = _hide(v2_auth_client, job, extra_qs=f"{BOARD_QS}&hide_empty=1")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["board"]["companies"] == []
    assert payload["board"]["meta"]["total_companies"] == 0
    follow = v2_auth_client.get("/api/board?country=uk&hide_empty=1").get_json()
    assert follow["companies"] == []


@pytest.mark.fresh_db
def test_not_for_me_on_newest_job_reorders_mutation_board(v2_auth_client, db, seeded_catalog_v2):
    from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog

    sync_company_board_to_catalog(
        "uk",
        {
            "name": "AAA Older Fetch",
            "city": "London",
            "size": "51-200",
            "careers_url": "https://boards.greenhouse.io/aaaolder",
            "ats_type": "greenhouse",
            "ats_url": "https://boards.greenhouse.io/aaaolder",
            "matching_jobs": [
                {
                    "title": "Backend Engineer",
                    "url": "https://boards.greenhouse.io/aaaolder/jobs/1?gh_jid=1",
                    "fetched": "2025-06-02T00:45:00+00:00",
                    "last_seen": "2025-06-02T00:45:00+00:00",
                }
            ],
            "added": "2025-06-01",
        },
    )
    acme = get_company("uk", ACME)
    jobs = list(acme.get("matching_jobs") or [])
    jobs.append(
        {
            "title": "Brand New Role",
            "url": "https://boards.greenhouse.io/acmebackend/jobs/999999?gh_jid=999999",
            "fetched": "2025-06-10T12:00:00+00:00",
            "last_seen": "2025-06-10T12:00:00+00:00",
        },
    )
    acme["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", acme)

    before = v2_auth_client.get("/api/board?country=uk&sort=newest").get_json()
    assert [row["name"] for row in before["companies"]] == [ACME, "AAA Older Fetch"]

    resp = v2_auth_client.post(
        f"/api/jobs/not-for-me?{BOARD_QS}",
        json={
            "country": "uk",
            "company": ACME,
            "url": "https://boards.greenhouse.io/acmebackend/jobs/999999?gh_jid=999999",
            "not_for_me": True,
            "reason": "wrong_location",
        },
    )
    assert resp.status_code == 200
    names = [row["name"] for row in resp.get_json()["board"]["companies"]]
    assert names == ["AAA Older Fetch", ACME]
    acme_row = next(row for row in resp.get_json()["board"]["companies"] if row["name"] == ACME)
    assert acme_row["newest_job_fetched"].startswith("2025-06-01")


@pytest.mark.fresh_db
def test_not_for_me_clamps_page_when_hide_empty_empties_current_page(v2_auth_client, db, tmp_path):
    import json

    data = {
        "source": "test",
        "companies": [
            {
                "name": "Alpha Co",
                "matching_jobs": [{
                    "title": "Eng",
                    "url": "https://example.com/alpha",
                    "fetched": "2026-09-02T00:00:00+00:00",
                }],
            },
            {
                "name": "Charlie Co",
                "matching_jobs": [{
                    "title": "Eng",
                    "url": "https://example.com/charlie",
                    "fetched": "2026-09-01T00:00:00+00:00",
                }],
            },
        ],
    }
    path = tmp_path / "mutation_board_pages.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    seed_country("uk", path)

    page_two = v2_auth_client.get(
        "/api/board?country=uk&hide_empty=1&sort=newest&page_size=1&page=2",
    ).get_json()
    assert [row["name"] for row in page_two["companies"]] == ["Charlie Co"]

    resp = v2_auth_client.post(
        "/api/jobs/not-for-me?include_board=1&country=uk&hide_empty=1&sort=newest&page_size=1&page=2",
        json={
            "country": "uk",
            "company": "Charlie Co",
            "url": "https://example.com/charlie",
            "not_for_me": True,
            "reason": "expired",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert [row["name"] for row in payload["board"]["companies"]] == ["Alpha Co"]
    assert payload["board"]["meta"]["page"] == 1
    assert payload["board"]["meta"]["total_pages"] == 1
    assert payload["board"]["meta"]["total_companies"] == 1
