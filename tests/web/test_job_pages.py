from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.credits.repo import list_ledger
from relocation_jobs.credits.service import credit_balance, spend_for_operation
from relocation_jobs.credits.types import CreditOperation
from relocation_jobs.positions.service import set_job_looking_to_apply
from relocation_jobs.users.entitlements import entitlement_status
from relocation_jobs.users.repo import create_user
from tests.helpers.seed import merge_and_save_jobs


def _publish_visa_job(seeded_catalog_v2) -> dict:
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    jobs = list(company["matching_jobs"])
    jobs[0]["visa_sponsorship"] = True
    jobs[0]["description_text"] = "<p>Build APIs in Go.</p>"
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", company)
    reloaded = get_company("uk", "Acme Backend Ltd")
    return next(j for j in reloaded["matching_jobs"] if j["url"] == jobs[0]["url"])


def _publish_visa_jobs(seeded_catalog_v2, count: int) -> list[dict]:
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    jobs = list(company["matching_jobs"])
    for job in jobs:
        job["visa_sponsorship"] = True
        job.setdefault("description_text", "<p>Build APIs in Go.</p>")
    next_id = 200000
    while len(jobs) < count:
        next_id += 1
        jobs.append(
            {
                "title": f"Visa Engineer {next_id}",
                "url": f"https://boards.greenhouse.io/acmebackend/jobs/{next_id}?gh_jid={next_id}",
                "visa_sponsorship": True,
                "description_text": "<p>Build APIs in Go.</p>",
            }
        )
    company["matching_jobs"] = jobs
    sync_company_board_to_catalog("uk", company)
    reloaded = get_company("uk", "Acme Backend Ltd")
    visa = [job for job in reloaded["matching_jobs"] if job.get("visa_sponsorship") is True]
    return visa[:count]


def _login_free(client, name: str) -> dict:
    user = create_user(name, email=f"{name}@example.com", google_sub=f"sub-{name}")
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess.permanent = True
    return user


def _public_save_spends(user_id: int) -> int:
    return sum(
        1
        for row in list_ledger(user_id)
        if row.get("event_type") == "spend" and row.get("operation") == "public_job_save"
    )


def test_job_page_renders_json_ld_without_redirect(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    resp = v2_client.get(f"/jobs/{job['public_slug']}", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'type="application/ld+json"' in body
    assert '"hiringOrganization"' in body
    assert '"name":"Kuchup"' in body
    assert "Track &amp; prepare this application in Kuchup" in body
    assert 'http-equiv="refresh"' not in body.lower()
    assert "Continue to the official" not in body
    assert f"/jobs/{job['public_slug']}/employer" not in body
    assert ">Sign in</a>" in body
    assert ">Open workspace</a>" not in body


def test_unknown_job_slug_is_404(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/jobs/not-a-real-role")
    assert resp.status_code == 404


def test_closed_job_returns_410(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    company = get_company("uk", "Acme Backend Ltd")
    other = next(j for j in company["matching_jobs"] if j["url"] != job["url"])
    merge_and_save_jobs(
        "uk",
        "Acme Backend Ltd",
        [{"title": other["title"], "url": other["url"]}],
    )
    resp = v2_client.get(f"/jobs/{job['public_slug']}")
    assert resp.status_code == 410
    body = resp.get_data(as_text=True)
    assert "This role has been closed" in body
    assert "/relocation-jobs-uk" in body
    assert "application/ld+json" not in body


def test_jobs_sitemap_lists_only_active_visa_slugs(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    resp = v2_client.get("/sitemap-jobs.xml")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f"/jobs/{job['public_slug']}" in body
    assert "<lastmod>" in body
    company = get_company("uk", "Acme Backend Ltd")
    other = next(j for j in company["matching_jobs"] if j["url"] != job["url"])
    assert other.get("public_slug")
    if other.get("visa_sponsorship") is not True:
        assert f"/jobs/{other['public_slug']}" not in body


def test_save_unauthenticated_redirects_to_google(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    resp = v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location") or ""
    parsed = urlparse(location)
    assert parsed.path == "/api/auth/google"
    assert unquote(parse_qs(parsed.query).get("next", [""])[0]) == f"/jobs/{job['public_slug']}/save"


def test_save_authenticated_lands_in_company_workspace(auth_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    resp = auth_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/company/uk/acme-backend-ltd" in (resp.headers.get("Location") or "")


def test_employer_outbound_redirects_to_ats(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    resp = v2_client.get(f"/jobs/{job['public_slug']}/employer", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert (resp.headers.get("Location") or "") == job["url"]


def test_three_public_saves_do_not_spend_credits(v2_client, seeded_catalog_v2):
    jobs = _publish_visa_jobs(seeded_catalog_v2, 4)
    user = _login_free(v2_client, "free-three")
    uid = int(user["id"])
    for job in jobs[:3]:
        resp = v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/company/uk/acme-backend-ltd" in (resp.headers.get("Location") or "")
    assert _public_save_spends(uid) == 0
    assert entitlement_status(uid)["public_job_saves_used"] == 3


def test_fourth_public_save_spends_one_credit(v2_client, seeded_catalog_v2):
    jobs = _publish_visa_jobs(seeded_catalog_v2, 4)
    user = _login_free(v2_client, "free-four")
    uid = int(user["id"])
    credit_balance(uid)
    for job in jobs[:3]:
        v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    before = credit_balance(uid).total
    resp = v2_client.get(f"/jobs/{jobs[3]['public_slug']}/save", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert _public_save_spends(uid) == 1
    assert credit_balance(uid).total == before - 1


def test_fourth_public_save_empty_wallet_stays_on_page(v2_client, seeded_catalog_v2):
    jobs = _publish_visa_jobs(seeded_catalog_v2, 4)
    user = _login_free(v2_client, "free-empty")
    uid = int(user["id"])
    credit_balance(uid)
    for index in range(30):
        spend_for_operation(
            uid,
            CreditOperation.ROLE_REPLACEMENT,
            idempotency_key=f"drain:{index}",
        )
    for job in jobs[:3]:
        v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    resp = v2_client.get(f"/jobs/{jobs[3]['public_slug']}/save", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Buy credits or Full Access to track more roles today" in body
    assert "/pricing" in body
    assert entitlement_status(uid)["public_job_saves_used"] == 3


def test_same_slug_save_does_not_increment(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    user = _login_free(v2_client, "free-dup")
    uid = int(user["id"])
    v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    assert entitlement_status(uid)["public_job_saves_used"] == 1
    assert _public_save_spends(uid) == 0


def test_board_looking_to_apply_does_not_count_public_save(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    user = _login_free(v2_client, "free-board")
    uid = int(user["id"])
    set_job_looking_to_apply("uk", "Acme Backend Ltd", job["url"], True, user_id=uid)
    assert entitlement_status(uid)["public_job_saves_used"] == 0
    resp = v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert entitlement_status(uid)["public_job_saves_used"] == 0


def test_employer_uncapped_after_daily_saves(v2_client, seeded_catalog_v2):
    jobs = _publish_visa_jobs(seeded_catalog_v2, 3)
    _login_free(v2_client, "free-employer")
    for job in jobs:
        v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    resp = v2_client.get(f"/jobs/{jobs[0]['public_slug']}/employer", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert (resp.headers.get("Location") or "") == jobs[0]["url"]


def test_signed_in_job_page_shows_employer_link(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    _login_free(v2_client, "free-employer-link")
    body = v2_client.get(f"/jobs/{job['public_slug']}").get_data(as_text=True)
    assert f"/jobs/{job['public_slug']}/employer" in body
    assert "Continue to the official" in body
    assert ">Open workspace</a>" in body
    assert ">Sign in</a>" not in body
    assert 'title="free-employer-link"' in body


def test_signed_in_job_page_shows_free_remaining_cta(v2_client, seeded_catalog_v2):
    job = _publish_visa_job(seeded_catalog_v2)
    _login_free(v2_client, "free-cta")
    resp = v2_client.get(f"/jobs/{job['public_slug']}")
    assert resp.status_code == 200
    assert "3 of 3 free today" in resp.get_data(as_text=True)


def test_signed_in_job_page_credit_cta_after_free_saves(v2_client, seeded_catalog_v2):
    jobs = _publish_visa_jobs(seeded_catalog_v2, 4)
    _login_free(v2_client, "free-cta-credit")
    for job in jobs[:3]:
        v2_client.get(f"/jobs/{job['public_slug']}/save", follow_redirects=False)
    resp = v2_client.get(f"/jobs/{jobs[3]['public_slug']}")
    assert resp.status_code == 200
    assert "Use 1 credit to track this role" in resp.get_data(as_text=True)
