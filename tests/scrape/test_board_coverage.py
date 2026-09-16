from __future__ import annotations

import pytest

from relocation_jobs.core.ats_constants import ATS_TYPE_CHOICES
from relocation_jobs.scrape.board import (
    assert_full_ats_coverage,
    fetch_ats_board,
    supported_ats_types,
)


def test_all_ats_type_choices_have_board_fetcher():
    assert_full_ats_coverage()
    assert supported_ats_types() == {key for key, _ in ATS_TYPE_CHOICES}


@pytest.mark.asyncio
async def test_fetch_ats_board_skips_playwright_required_without_browser(monkeypatch):
    monkeypatch.setattr("relocation_jobs.scrape.board.PLAYWRIGHT_AVAILABLE", False)
    company = {
        "name": "Mobile.de",
        "ats_type": "hibob",
        "ats_url": "https://mobilede.careers.hibob.com/jobs",
        "careers_url": "https://mobilede.careers.hibob.com/jobs",
    }
    with pytest.raises(LookupError, match="Playwright not installed"):
        await fetch_ats_board(None, company)
