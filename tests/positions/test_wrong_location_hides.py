from __future__ import annotations

import inspect

import pytest

from relocation_jobs.catalog.repo import update_matching_job_fields
from relocation_jobs.companies.service import update_company_city
from relocation_jobs.core.job_identity import normalize_job_url
from relocation_jobs.panel.service import flatten_companies
from relocation_jobs.positions import service as positions
from relocation_jobs.positions.state import derive_bucket
from relocation_jobs.positions.types import PositionBucket, TrackingFlags
from relocation_jobs.users.repo import load_job_tracking


def _company_and_jobs(catalog: dict) -> tuple[str, str, str]:
    acme = catalog["companies"][0]
    return acme["name"], acme["matching_jobs"][0]["url"], acme["matching_jobs"][1]["url"]


def _flatten(user_id: int) -> dict:
    companies, _, _ = flatten_companies("uk", user_id=user_id)
    return next(c for c in companies if c["name"] == "Acme Backend Ltd")


def _urls(jobs: list[dict]) -> set[str]:
    return {j["url"] for j in jobs}


def _track_for(user_id: int, company: str, url: str) -> dict | None:
    tracking = load_job_tracking(user_id, country="uk")
    return tracking.get(("uk", company, normalize_job_url(url)))


def _set_job_location(company: str, url: str, location: str) -> None:
    update_matching_job_fields("uk", company, lookup_url=url, location=location)


def _london_office(company: str) -> None:
    update_company_city(
        "uk",
        company,
        locations=[{"country": "uk", "city": "London"}],
    )


def _london_office_wrong_city_job(
    company: str,
    wrong_url: str,
    *,
    keep_url: str | None = None,
    wrong_location: str = "Paris, France",
) -> None:
    _london_office(company)
    _set_job_location(company, wrong_url, wrong_location)
    if keep_url:
        _set_job_location(company, keep_url, "")


@pytest.mark.integration
class TestApplyWrongLocationHides:
    @pytest.fixture(autouse=True)
    def _clear_job_locations(self, seeded_catalog_v2):
        yield
        acme = seeded_catalog_v2["companies"][0]
        company = acme["name"]
        for job in acme["matching_jobs"]:
            _set_job_location(company, job["url"], "")

    def test_marks_failing_job_and_skips_matching_sibling(
        self, seeded_catalog_v2, test_user
    ):
        uid = test_user["id"]
        company, paris_url, london_url = _company_and_jobs(seeded_catalog_v2)
        _london_office_wrong_city_job(company, paris_url, keep_url=london_url)

        marked = positions.apply_wrong_location_hides(uid, country_key="uk")
        assert marked == 1

        paris = _track_for(uid, company, paris_url)
        assert paris is not None
        assert int(paris.get("not_for_me") or 0) == 1
        assert paris.get("not_for_me_reason") == "wrong_location"

        london = _track_for(uid, company, london_url)
        assert not london or not int(london.get("not_for_me") or 0)

    def test_skips_user_chosen_hide_reasons(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url_a, url_b = _company_and_jobs(seeded_catalog_v2)
        _london_office(company)
        _set_job_location(company, url_a, "Paris, France")
        _set_job_location(company, url_b, "Berlin")

        positions.set_job_not_for_me(
            "uk", company, url_a, user_id=uid, not_for_me=True, reason="expired",
        )
        marked = positions.apply_wrong_location_hides(uid, country_key="uk")
        assert marked == 1

        expired = _track_for(uid, company, url_a)
        assert expired is not None
        assert expired.get("not_for_me_reason") == "expired"

        hidden = _track_for(uid, company, url_b)
        assert hidden is not None
        assert hidden.get("not_for_me_reason") == "wrong_location"

    def test_skips_location_gate_override(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url, other = _company_and_jobs(seeded_catalog_v2)
        _london_office_wrong_city_job(company, url, keep_url=other)

        positions.apply_wrong_location_hides(uid, country_key="uk")
        positions.set_job_not_for_me("uk", company, url, user_id=uid, not_for_me=False)

        marked = positions.apply_wrong_location_hides(uid, country_key="uk")
        assert marked == 0
        acme = _flatten(uid)
        assert url in _urls(acme["jobs"])
        assert url not in _urls(acme["not_for_me_jobs"])

    def test_second_apply_is_noop(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url, other = _company_and_jobs(seeded_catalog_v2)
        _london_office_wrong_city_job(company, url, keep_url=other)

        first = positions.apply_wrong_location_hides(uid, country_key="uk")
        row = _track_for(uid, company, url)
        assert first == 1
        assert row is not None
        stamped = row.get("not_for_me_date")

        second = positions.apply_wrong_location_hides(uid, country_key="uk")
        again = _track_for(uid, company, url)
        assert second == 0
        assert again is not None
        assert again.get("not_for_me_date") == stamped
        assert again.get("not_for_me_reason") == "wrong_location"

    def test_reconcile_restores_when_city_added(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url, other = _company_and_jobs(seeded_catalog_v2)
        update_company_city(
            "uk",
            company,
            locations=[{"country": "uk", "city": "Edinburgh"}],
        )
        _set_job_location(company, url, "London")
        _set_job_location(company, other, "")
        positions.apply_wrong_location_hides(uid, country_key="uk")

        update_company_city(
            "uk",
            company,
            locations=[
                {"country": "uk", "city": "Edinburgh"},
                {"country": "uk", "city": "London"},
            ],
        )
        restored = positions.reconcile_wrong_location_hides(uid, country_key="uk")
        assert restored == 1

        acme = _flatten(uid)
        assert url in _urls(acme["jobs"])
        assert url not in _urls(acme["not_for_me_jobs"])

    def test_board_flatten_uses_persisted_row(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url, other = _company_and_jobs(seeded_catalog_v2)
        _london_office_wrong_city_job(company, url, keep_url=other)
        positions.apply_wrong_location_hides(uid, country_key="uk")

        track = _track_for(uid, company, url)
        flags = TrackingFlags.from_row(track)
        assert derive_bucket(flags, wrong_location=False) == PositionBucket.NOT_FOR_ME

        acme = _flatten(uid)
        assert url not in _urls(acme["jobs"])
        assert url in _urls(acme["not_for_me_jobs"])
        hidden = next(j for j in acme["not_for_me_jobs"] if j["url"] == url)
        assert hidden["not_for_me_reason"] == "wrong_location"
        assert other in _urls(acme["jobs"])

    def test_flatten_does_not_write_tracking_rows(self, seeded_catalog_v2, test_user):
        uid = test_user["id"]
        company, url, other = _company_and_jobs(seeded_catalog_v2)
        _london_office_wrong_city_job(company, url, keep_url=other)

        acme = _flatten(uid)
        assert url in _urls(acme["not_for_me_jobs"])
        assert not load_job_tracking(uid, country="uk")


def test_board_read_path_does_not_apply_wrong_location_hides():
    from relocation_jobs.web.routes import board

    assert "apply_wrong_location_hides" not in inspect.getsource(board)


def test_fetch_and_location_edits_wire_apply():
    from relocation_jobs.fetch import runner
    from relocation_jobs.web.routes import catalog, companies

    assert "apply_wrong_location_hides" in inspect.getsource(runner)
    assert "apply_wrong_location_hides" in inspect.getsource(companies)
    assert "apply_wrong_location_hides" in inspect.getsource(catalog)
