from __future__ import annotations

from relocation_jobs.broadcast.types import CapacityLimits
from relocation_jobs.opportunities.reconcile import reconcile_sticky_slots
from relocation_jobs.opportunities.types import CompanyCandidate, OpportunityRow


def test_reconcile_keeps_sticky_when_newer_companies_appear():
    limits = CapacityLimits(company_slots=2, jobs_per_company=3, total_position_budget=30)
    existing = [
        OpportunityRow(
            country="germany",
            company_name="StepStone",
            newest_fetched="2026-01-01",
            revealed_job_count=3,
            engaged=True,
        ),
        OpportunityRow(
            country="germany",
            company_name="OldCo",
            newest_fetched="2026-01-02",
            revealed_job_count=2,
            engaged=False,
        ),
    ]
    ranked = [
        CompanyCandidate(
            country="germany",
            company_name="FlicksBoss",
            newest_fetched="2026-08-01",
            open_job_count=5,
        ),
        CompanyCandidate(
            country="germany",
            company_name="RedCare",
            newest_fetched="2026-07-01",
            open_job_count=4,
        ),
        CompanyCandidate(
            country="germany",
            company_name="StepStone",
            newest_fetched="2026-06-01",
            open_job_count=3,
        ),
        CompanyCandidate(
            country="germany",
            company_name="OldCo",
            newest_fetched="2026-05-01",
            open_job_count=2,
        ),
    ]
    rows = reconcile_sticky_slots(
        existing=existing,
        ranked_open=ranked,
        prefs_countries={"germany"},
        limits=limits,
        is_admin=False,
    )
    names = {r.company_name for r in rows}
    assert "StepStone" in names
    assert "OldCo" in names
    assert len(rows) == 2
    assert "FlicksBoss" not in names


def test_reconcile_fills_vacant_with_newest_open():
    limits = CapacityLimits(company_slots=2, jobs_per_company=3, total_position_budget=30)
    existing = [
        OpportunityRow(
            country="germany",
            company_name="StepStone",
            newest_fetched="2026-01-01",
            revealed_job_count=3,
            engaged=True,
        ),
    ]
    ranked = [
        CompanyCandidate(
            country="germany",
            company_name="FlicksBoss",
            newest_fetched="2026-08-01",
            open_job_count=5,
        ),
        CompanyCandidate(
            country="germany",
            company_name="StepStone",
            newest_fetched="2026-06-01",
            open_job_count=3,
        ),
    ]
    rows = reconcile_sticky_slots(
        existing=existing,
        ranked_open=ranked,
        prefs_countries={"germany"},
        limits=limits,
        is_admin=False,
    )
    assert {r.company_name for r in rows} == {"StepStone", "FlicksBoss"}
    flick = next(r for r in rows if r.company_name == "FlicksBoss")
    assert flick.revealed_job_count == 0


def test_reconcile_drops_empty_unengaged_but_keeps_engaged_company():
    limits = CapacityLimits(company_slots=2, jobs_per_company=3, total_position_budget=30)
    existing = [
        OpportunityRow(country="germany", company_name="Empty", engaged=False),
        OpportunityRow(country="germany", company_name="Saved", engaged=True),
    ]
    ranked = [
        CompanyCandidate(
            country="germany",
            company_name="Fresh",
            newest_fetched="2026-08-01",
            open_job_count=4,
        ),
    ]
    rows = reconcile_sticky_slots(
        existing=existing,
        ranked_open=ranked,
        prefs_countries={"germany"},
        limits=limits,
        is_admin=False,
    )
    assert {row.company_name for row in rows} == {"Saved", "Fresh"}
