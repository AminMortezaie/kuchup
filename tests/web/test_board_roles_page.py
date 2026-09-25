from __future__ import annotations

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.panel.roles_page import BOARD_ROLES_PAGE_SIZE


def _seed_roles(jobs: list[dict], company_name: str = "Acme Backend Ltd") -> None:
    company = get_company("uk", company_name)
    assert company is not None
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", company)


def _role(
    title: str,
    *,
    idx: int,
    matches_default: int = 1,
    day: int | None = None,
) -> dict:
    stamp_day = day if day is not None else (idx % 9) + 1
    return {
        "title": title,
        "url": (
            f"https://boards.greenhouse.io/acmebackend/jobs/{2000 + idx}"
            f"?gh_jid={2000 + idx}"
        ),
        "fetched": f"2025-06-{stamp_day:02d}T12:00:00+00:00",
        "last_seen": f"2025-06-{stamp_day:02d}T12:00:00+00:00",
        "visa_sponsorship": True,
        "matches_default_filter": matches_default,
    }


def _seed_many_open_roles(company_name: str = "Acme Backend Ltd", count: int = 8) -> None:
    _seed_roles(
        [_role(f"Engineer {i}", idx=i) for i in range(count)],
        company_name=company_name,
    )


def _company_from_board(client, name: str = "Acme Backend Ltd") -> dict:
    payload = client.get("/api/board?country=uk").get_json()
    return next(c for c in payload["companies"] if c["name"] == name)


def _fetch_more(client, *, company: str = "Acme Backend Ltd", offset: int) -> dict:
    page = client.get(
        "/api/board/company-roles"
        f"?company_country=uk&company={company.replace(' ', '%20')}"
        f"&offset={offset}"
    )
    assert page.status_code == 200
    return page.get_json()


def _titles(jobs: list[dict]) -> list[str]:
    return [job["title"] for job in jobs]


def _add_personal_exclude(client, keyword: str) -> None:
    resp = client.post(
        "/api/role-preferences/mine",
        json={"keyword": keyword, "kind": "exclude"},
    )
    assert resp.status_code == 201


def _disable_global_include(client, keyword: str) -> None:
    tags = client.get("/api/role-preferences").get_json()["tags"]
    tag = next(item for item in tags if item["keyword"] == keyword and item["kind"] == "include")
    resp = client.put(f"/api/role-preferences/{tag['id']}", json={"enabled": False})
    assert resp.status_code == 200


def test_board_returns_first_three_roles_per_company(v2_auth_client, seeded_catalog_v2):
    del seeded_catalog_v2
    _seed_many_open_roles(count=8)
    acme = _company_from_board(v2_auth_client)
    assert acme["job_count"] == 8
    assert len(acme["jobs"]) == BOARD_ROLES_PAGE_SIZE
    assert acme["jobs_more"] == 8 - BOARD_ROLES_PAGE_SIZE


def test_board_company_roles_loads_next_page(v2_auth_client, seeded_catalog_v2):
    del seeded_catalog_v2
    _seed_many_open_roles(count=8)
    acme = _company_from_board(v2_auth_client)
    first_keys = {(j.get("idempotency_key") or j["url"]) for j in acme["jobs"]}
    body = _fetch_more(v2_auth_client, offset=BOARD_ROLES_PAGE_SIZE)
    assert len(body["jobs"]) == BOARD_ROLES_PAGE_SIZE
    assert body["jobs_more"] == 8 - 2 * BOARD_ROLES_PAGE_SIZE
    second_keys = {(j.get("idempotency_key") or j["url"]) for j in body["jobs"]}
    assert first_keys.isdisjoint(second_keys)


def test_exclude_filter_keeps_roles_out_of_initial_and_fetch_more(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Backend Engineer Alpha", idx=0, day=9),
        _role("Hidden Intern Role", idx=1, day=8),
        _role("Backend Engineer Bravo", idx=2, day=7),
        _role("Backend Engineer Charlie", idx=3, day=6),
        _role("Backend Engineer Delta", idx=4, day=5),
        _role("Backend Engineer Echo", idx=5, day=4),
    ])
    _add_personal_exclude(v2_auth_client, "intern")

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert "Hidden Intern Role" not in first
    assert len(first) == BOARD_ROLES_PAGE_SIZE
    assert acme["jobs_more"] == 2

    more = _fetch_more(v2_auth_client, offset=len(first))
    second = _titles(more["jobs"])
    assert "Hidden Intern Role" not in second
    assert len(second) == 2
    assert more["jobs_more"] == 0
    assert set(first).isdisjoint(set(second))


def test_include_filter_keeps_non_matching_roles_out_of_both_buckets(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Python Developer Alpha", idx=0, day=9),
        _role("Backend Architect Only", idx=1, day=8),
        _role("Python Developer Bravo", idx=2, day=7),
        _role("Backend Niche Role", idx=3, day=6),
        _role("Python Developer Charlie", idx=4, day=5),
        _role("Python Developer Delta", idx=5, day=4),
    ])
    _disable_global_include(v2_auth_client, "backend")

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert "Backend Architect Only" not in first
    assert "Backend Niche Role" not in first
    assert len(first) == BOARD_ROLES_PAGE_SIZE

    more = _fetch_more(v2_auth_client, offset=len(first))
    second = _titles(more["jobs"])
    assert "Backend Architect Only" not in second
    assert "Backend Niche Role" not in second
    assert all(title.startswith("Python Developer") for title in first + second)


def test_mixed_include_and_exclude_return_only_eligible_roles(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Python Developer Alpha", idx=0, day=9),
        _role("Backend Architect Only", idx=1, day=8),
        _role("Python Intern Developer", idx=2, day=7),
        _role("Python Developer Bravo", idx=3, day=6),
        _role("Python Developer Charlie", idx=4, day=5),
        _role("Python Developer Delta", idx=5, day=4),
        _role("Python Developer Echo", idx=6, day=3),
    ])
    _disable_global_include(v2_auth_client, "backend")
    _add_personal_exclude(v2_auth_client, "intern")

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    more = _fetch_more(v2_auth_client, offset=len(first))
    all_titles = first + _titles(more["jobs"])

    assert "Backend Architect Only" not in all_titles
    assert "Python Intern Developer" not in all_titles
    assert all_titles == [
        "Python Developer Alpha",
        "Python Developer Bravo",
        "Python Developer Charlie",
        "Python Developer Delta",
        "Python Developer Echo",
    ]
    assert len(first) == BOARD_ROLES_PAGE_SIZE
    assert len(more["jobs"]) == 2
    assert more["jobs_more"] == 0


def test_fetch_more_paginates_filtered_set_not_raw_indexes(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Backend Engineer A", idx=0, day=9),
        _role("Excluded Intern B", idx=1, day=8),
        _role("Backend Engineer C", idx=2, day=7),
        _role("Excluded Intern D", idx=3, day=6),
        _role("Backend Engineer E", idx=4, day=5),
        _role("Backend Engineer F", idx=5, day=4),
        _role("Backend Engineer G", idx=6, day=3),
        _role("Backend Engineer H", idx=7, day=2),
    ])
    _add_personal_exclude(v2_auth_client, "intern")

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert first == [
        "Backend Engineer A",
        "Backend Engineer C",
        "Backend Engineer E",
    ]
    assert acme["jobs_more"] == 3

    more = _fetch_more(v2_auth_client, offset=len(first))
    second = _titles(more["jobs"])
    assert second == [
        "Backend Engineer F",
        "Backend Engineer G",
        "Backend Engineer H",
    ]
    assert more["jobs_more"] == 0
    assert set(first).isdisjoint(set(second))
    assert "Excluded Intern B" not in first + second
    assert "Excluded Intern D" not in first + second


def test_insufficient_eligible_roles_never_pads_with_filtered_out(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Backend Engineer A", idx=0, day=9),
        _role("Excluded Intern B", idx=1, day=8),
        _role("Backend Engineer C", idx=2, day=7),
        _role("Excluded Intern D", idx=3, day=6),
        _role("Backend Engineer E", idx=4, day=5),
        _role("Excluded Intern F", idx=5, day=4),
        _role("Backend Engineer G", idx=6, day=3),
    ])
    _add_personal_exclude(v2_auth_client, "intern")

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert first == [
        "Backend Engineer A",
        "Backend Engineer C",
        "Backend Engineer E",
    ]
    assert acme["jobs_more"] == 1

    more = _fetch_more(v2_auth_client, offset=len(first))
    assert _titles(more["jobs"]) == ["Backend Engineer G"]
    assert more["jobs_more"] == 0
    assert all("Intern" not in title for title in first + _titles(more["jobs"]))


def test_fetch_more_respects_preference_change_between_requests(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Backend Engineer A", idx=0, day=9),
        _role("Backend Engineer B", idx=1, day=8),
        _role("Backend Engineer C", idx=2, day=7),
        _role("Backend Engineer D", idx=3, day=6),
        _role("Backend Specialist E", idx=4, day=5),
        _role("Backend Engineer F", idx=5, day=4),
        _role("Backend Engineer G", idx=6, day=3),
    ])

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert first == [
        "Backend Engineer A",
        "Backend Engineer B",
        "Backend Engineer C",
    ]

    _add_personal_exclude(v2_auth_client, "specialist")
    more = _fetch_more(v2_auth_client, offset=len(first))
    second = _titles(more["jobs"])
    assert "Backend Specialist E" not in second
    assert second == [
        "Backend Engineer D",
        "Backend Engineer F",
        "Backend Engineer G",
    ]
    assert more["jobs_more"] == 0


def test_nondefault_roles_do_not_leak_into_fetch_more_without_prefs(
    v2_auth_client, seeded_catalog_v2,
):
    del seeded_catalog_v2
    _seed_roles([
        _role("Backend Engineer A", idx=0, day=9),
        _role("Backend Engineer B", idx=1, day=8),
        _role("Backend Engineer C", idx=2, day=7),
        _role("Backend Engineer D", idx=3, day=6),
        _role("Backend Engineer E", idx=4, day=5),
        _role("Backend Engineer F", idx=5, day=4),
        _role("Engineering Manager Hidden", idx=6, day=3, matches_default=0),
    ])

    acme = _company_from_board(v2_auth_client)
    first = _titles(acme["jobs"])
    assert first == [
        "Backend Engineer A",
        "Backend Engineer B",
        "Backend Engineer C",
    ]
    assert "Engineering Manager Hidden" not in first
    assert acme["jobs_more"] == 3

    more = _fetch_more(v2_auth_client, offset=len(first))
    second = _titles(more["jobs"])
    assert second == [
        "Backend Engineer D",
        "Backend Engineer E",
        "Backend Engineer F",
    ]
    assert "Engineering Manager Hidden" not in second
    assert more["jobs_more"] == 0
