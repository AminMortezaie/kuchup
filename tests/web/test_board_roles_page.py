from __future__ import annotations

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.panel.roles_page import BOARD_ROLES_PAGE_SIZE


def _seed_many_open_roles(company_name: str = "Acme Backend Ltd", count: int = 8) -> None:
    company = get_company("uk", company_name)
    assert company is not None
    jobs = []
    for i in range(count):
        jobs.append({
            "title": f"Engineer {i}",
            "url": f"https://boards.greenhouse.io/acmebackend/jobs/{1000 + i}?gh_jid={1000 + i}",
            "fetched": f"2025-06-0{(i % 9) + 1}T12:00:00+00:00",
            "last_seen": f"2025-06-0{(i % 9) + 1}T12:00:00+00:00",
            "visa_sponsorship": True,
        })
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", company)


def test_board_returns_first_three_roles_per_company(v2_auth_client, seeded_catalog_v2):
    del seeded_catalog_v2
    _seed_many_open_roles(count=8)
    payload = v2_auth_client.get("/api/board?country=uk").get_json()
    acme = next(c for c in payload["companies"] if c["name"] == "Acme Backend Ltd")
    assert acme["job_count"] == 8
    assert len(acme["jobs"]) == BOARD_ROLES_PAGE_SIZE
    assert acme["jobs_more"] == 8 - BOARD_ROLES_PAGE_SIZE
    assert payload["meta"]["roles_page_size"] == BOARD_ROLES_PAGE_SIZE


def test_board_company_roles_loads_next_page(v2_auth_client, seeded_catalog_v2):
    del seeded_catalog_v2
    _seed_many_open_roles(count=8)
    first = v2_auth_client.get("/api/board?country=uk").get_json()
    acme = next(c for c in first["companies"] if c["name"] == "Acme Backend Ltd")
    first_keys = {(j.get("idempotency_key") or j["url"]) for j in acme["jobs"]}
    page = v2_auth_client.get(
        "/api/board/company-roles"
        "?company_country=uk&company=Acme%20Backend%20Ltd&bucket=jobs"
        f"&offset={BOARD_ROLES_PAGE_SIZE}&limit={BOARD_ROLES_PAGE_SIZE}"
    )
    assert page.status_code == 200
    body = page.get_json()
    assert body["bucket"] == "jobs"
    assert len(body["jobs"]) == BOARD_ROLES_PAGE_SIZE
    assert body["jobs_more"] == 8 - 2 * BOARD_ROLES_PAGE_SIZE
    second_keys = {(j.get("idempotency_key") or j["url"]) for j in body["jobs"]}
    assert first_keys.isdisjoint(second_keys)
