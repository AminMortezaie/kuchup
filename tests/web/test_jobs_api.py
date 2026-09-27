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


def test_free_user_unlock_role_spends_credit(client, db, seeded_catalog_v2, monkeypatch):
    from relocation_jobs.broadcast import service as broadcast_service
    from relocation_jobs.credits.service import credit_balance
    from relocation_jobs.users.repo import create_user
    from tests.helpers.seed import append_matching_jobs, ensure_company_assignments, seed_free_assignments

    user = create_user(
        "free-unlock",
        email="free-unlock@example.com",
        google_sub="sub-free-unlock",
    )
    uid = int(user["id"])
    seed_free_assignments(uid, ["uk"])
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["username"] = user["username"]
        sess.permanent = True
    from relocation_jobs.broadcast import repo as broadcast_repo

    jobs = append_matching_jobs(
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
    period = broadcast_repo.current_period_key()
    ensure_company_assignments(
        uid,
        "uk",
        "Acme Backend Ltd",
        jobs,
        active_target=3,
        period_key=period,
    )
    listing = client.get("/api/jobs?country=uk").get_json()
    company = next(item for item in listing["companies"] if item["name"] == "Acme Backend Ltd")
    job = company["jobs"][0]
    credit_balance(uid)
    before = credit_balance(uid).total
    monkeypatch.setattr(
        broadcast_service,
        "enqueue_replace_assignment",
        lambda *args, **kwargs: {"queued": True, "synced": False},
    )
    resp = client.post(
        "/api/jobs/unlock-role",
        json={
            "country": "uk",
            "company": company["name"],
            "url": job["url"],
            "idempotency_key": job.get("idempotency_key") or "",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["reveal"]["expanded"] is True
    assert payload["reveal"]["credits_spent"] == 1
    assert credit_balance(uid).total == before - 1


def test_free_user_unlock_role_empty_wallet_returns_402(client, db, seeded_catalog_v2):
    from relocation_jobs.broadcast import repo as broadcast_repo
    from relocation_jobs.credits import repo as credits_repo
    from relocation_jobs.credits.service import credit_balance
    from relocation_jobs.users.repo import create_user
    from tests.helpers.seed import append_matching_jobs, ensure_company_assignments, seed_free_assignments

    user = create_user(
        "free-unlock-empty",
        email="free-unlock-empty@example.com",
        google_sub="sub-free-unlock-empty",
    )
    uid = int(user["id"])
    seed_free_assignments(uid, ["uk"])
    jobs = append_matching_jobs(
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
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["username"] = user["username"]
        sess.permanent = True
    period = broadcast_repo.current_period_key()
    ensure_company_assignments(
        uid,
        "uk",
        "Acme Backend Ltd",
        jobs,
        active_target=3,
        period_key=period,
    )
    listing = client.get("/api/jobs?country=uk").get_json()
    company = next(item for item in listing["companies"] if item["name"] == "Acme Backend Ltd")
    job = company["jobs"][0]
    credit_balance(uid)
    for index in range(30):
        credits_repo.spend_credits(
            uid,
            cost=1,
            operation="test",
            idempotency_key=f"drain-unlock:{index}",
        )
    resp = client.post(
        "/api/jobs/unlock-role",
        json={
            "country": "uk",
            "company": company["name"],
            "url": job["url"],
            "idempotency_key": job.get("idempotency_key") or "",
        },
    )
    assert resp.status_code == 402
    assert "credits" in (resp.get_json().get("error") or "").lower()


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
