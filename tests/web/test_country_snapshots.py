from __future__ import annotations

import importlib.util
from pathlib import Path

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "export_homepage_country_snapshots.py"
_SPEC = importlib.util.spec_from_file_location("export_homepage_country_snapshots", _SCRIPTS)
assert _SPEC is not None and _SPEC.loader is not None
_EXPORT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EXPORT)


def test_weekly_sample_rotates_by_iso_week():
    rows = [{"i": n} for n in range(10)]
    first = _EXPORT._weekly_sample(rows, 3, week=1)
    second = _EXPORT._weekly_sample(rows, 3, week=2)
    assert first != second
    assert [row["i"] for row in first] == [1, 2, 3]
    assert [row["i"] for row in second] == [2, 3, 4]


def test_country_snapshot_links_sample_positions_to_employer_ats(seeded_catalog_v2):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"][0]["visa_sponsorship"] = True
    company["matching_jobs"][1]["visa_sponsorship"] = False
    sync_company_board_to_catalog("uk", company)

    snap = _EXPORT._snapshot_for_country("uk", {"jobs": 1, "visa_jobs": 1}, {})

    assert snap["sample_positions"]
    url = snap["sample_positions"][0]["url"]
    assert url.startswith("https://boards.greenhouse.io/")
    assert not url.startswith("/jobs/")
    assert "kuchup.com/jobs/" not in url
