from __future__ import annotations


def test_jobs_list_returns_companies(v2_auth_client, seeded_catalog_v2):
    resp = v2_auth_client.get("/api/jobs?country=uk")
    assert resp.status_code == 200
    payload = resp.get_json()
    companies = payload["companies"]
    stats = payload["stats"]
    assert len(companies) == 1
    assert companies[0]["name"] == "Acme Backend Ltd"
    assert len(companies[0]["jobs"]) == 2
    assert stats["total_jobs"] == 2
    assert stats["companies_with_jobs"] == 1


def test_free_user_jobs_list_caps_positions(client, db, seeded_catalog_v2):
    from tests.helpers.seed import seed_free_assignments
    from relocation_jobs.users.repo import create_user
    from tests.helpers.seed import append_matching_jobs

    append_matching_jobs(
        "uk",
        "Acme Backend Ltd",
        [
            {
                "title": f"Engineer {index}",
                "url": (
                    f"https://boards.greenhouse.io/acmebackend/jobs/{index}00000"
                    f"?gh_jid={index}00000"
                ),
                "fetched": "2025-06-01",
                "last_seen": "2025-06-01",
            }
            for index in range(3, 6)
        ],
    )
    user = create_user(
        "freejobslist",
        email="freejobslist@example.com",
        google_sub="sub-free-jobs-list",
    )
    seed_free_assignments(int(user["id"]), ["uk"])
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True
    payload = client.get("/api/jobs?country=uk").get_json()
    acme = next(company for company in payload["companies"] if company["name"] == "Acme Backend Ltd")
    assert len(acme["jobs"]) == 3
    assert acme["jobs_hidden_count"] == 2


def test_jobs_applied_marks_position(v2_auth_client, seeded_catalog_v2):
    listing = v2_auth_client.get("/api/jobs?country=uk").get_json()
    company = listing["companies"][0]
    job = company["jobs"][0]
    ctx = {"country": "uk", "company": company["name"], "url": job["url"]}
    resp = v2_auth_client.post("/api/jobs/applied", json={**ctx, "applied": True})
    assert resp.status_code == 200
    assert resp.get_json()["applied"] is True

    refreshed = v2_auth_client.get("/api/jobs?country=uk&position_applied_only=1").get_json()
    assert len(refreshed["companies"]) == 1
    assert refreshed["companies"][0]["jobs"][0]["applied"] is True
