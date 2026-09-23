from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from relocation_jobs.core.ats_constants import ATS_TYPE_CHOICES, PLAYWRIGHT_REQUIRED_ATS
from relocation_jobs.core.ats_detection import PLAYWRIGHT_AVAILABLE
from relocation_jobs.fetch.log import log_event
from relocation_jobs.scrape.go_http import go_board_jobs, http_scrape_mode
from relocation_jobs.scrape.boards.ashby import fetch_ashby_board
from relocation_jobs.scrape.boards.bol import fetch_bol_board
from relocation_jobs.scrape.boards.deel import fetch_deel_board
from relocation_jobs.scrape.ats_resolve import ensure_company_ats
from relocation_jobs.scrape.boards.generic import fetch_generic_board
from relocation_jobs.scrape.boards.greenhouse import fetch_greenhouse_board
from relocation_jobs.scrape.boards.hibob import fetch_hibob_board
from relocation_jobs.scrape.boards.http_sync import (
    fetch_applytojob_board,
    fetch_bamboo_board,
    fetch_epam_board,
    fetch_hirehive_board,
    fetch_movingimage_board,
    fetch_project_a_board,
    fetch_rss_board,
)
from relocation_jobs.scrape.boards.job_shop import fetch_job_shop_board
from relocation_jobs.scrape.boards.joblet import fetch_joblet_board
from relocation_jobs.scrape.boards.join import fetch_join_board
from relocation_jobs.scrape.boards.kake import fetch_kake_board
from relocation_jobs.scrape.boards.lever import fetch_lever_board
from relocation_jobs.scrape.boards.personio import fetch_personio_board
from relocation_jobs.scrape.boards.pinpointhq import fetch_pinpointhq_board
from relocation_jobs.scrape.boards.playwright_ats import (
    fetch_atlassian_board,
    fetch_jibe_board,
)
from relocation_jobs.scrape.boards.recruitee import fetch_recruitee_board
from relocation_jobs.scrape.boards.remotedxb import fetch_remotedxb_board
from relocation_jobs.scrape.boards.remoteok import fetch_remoteok_board
from relocation_jobs.scrape.boards.smartrecruiters import fetch_smartrecruiters_board
from relocation_jobs.scrape.boards.successfactors import fetch_successfactors_board
from relocation_jobs.scrape.boards.teamtailor import fetch_teamtailor_board
from relocation_jobs.scrape.boards.workable import fetch_workable_board
from relocation_jobs.scrape.boards.workday import fetch_workday_board

BoardFetcher = Callable[..., Awaitable[list[dict]]]

_BOARD_FETCHERS: dict[str, BoardFetcher] = {
    "ashby": fetch_ashby_board,
    "atlassian": fetch_atlassian_board,
    "applytojob": fetch_applytojob_board,
    "bamboohr": fetch_bamboo_board,
    "bol": fetch_bol_board,
    "deel": fetch_deel_board,
    "epam": fetch_epam_board,
    "greenhouse": fetch_greenhouse_board,
    "greenhouse_eu": fetch_greenhouse_board,
    "hibob": fetch_hibob_board,
    "hirehive": fetch_hirehive_board,
    "jibe": fetch_jibe_board,
    "job_shop": fetch_job_shop_board,
    "joblet": fetch_joblet_board,
    "join": fetch_join_board,
    "kake": fetch_kake_board,
    "lever": fetch_lever_board,
    "lever_eu": fetch_lever_board,
    "movingimage": fetch_movingimage_board,
    "personio": fetch_personio_board,
    "pinpointhq": fetch_pinpointhq_board,
    "project_a": fetch_project_a_board,
    "recruitee": fetch_recruitee_board,
    "remotedxb": fetch_remotedxb_board,
    "remoteok": fetch_remoteok_board,
    "rss": fetch_rss_board,
    "smartrecruiters": fetch_smartrecruiters_board,
    "successfactors": fetch_successfactors_board,
    "teamtailor": fetch_teamtailor_board,
    "workable": fetch_workable_board,
    "workday": fetch_workday_board,
}

_SUPPORTED_ATS = frozenset(_BOARD_FETCHERS)
_GENERIC_ATS = frozenset({"", "generic"})
_GO_EMPTY_TO_PYTHON = frozenset({"", "generic", "teamtailor"})


class UnsupportedAtsTypeError(LookupError):
    def __init__(self, ats_type: str):
        self.ats_type = ats_type
        super().__init__(f"Unsupported ATS type for v2 board fetch: {ats_type or 'unknown'}")


def supported_ats_types() -> frozenset[str]:
    return _SUPPORTED_ATS


def assert_full_ats_coverage() -> None:
    missing = {key for key, _ in ATS_TYPE_CHOICES} - _SUPPORTED_ATS
    if missing:
        raise RuntimeError(f"v2 board fetch missing ATS types: {sorted(missing)}")


async def fetch_ats_board(
    client,
    company: dict,
    *,
    sync_board=None,
    **kwargs,
) -> list[dict]:
    name = company.get("name") or "company"
    await ensure_company_ats(client, company, sync_board=sync_board)
    ats_type = (company.get("ats_type") or "").strip().lower()
    board_url = (company.get("ats_url") or company.get("careers_url") or "").strip()
    if not board_url:
        raise LookupError(f"No careers or ATS URL for {name}")

    log_event(f"fetching board ats={ats_type} url={board_url}", company=name)

    if ats_type in PLAYWRIGHT_REQUIRED_ATS and not PLAYWRIGHT_AVAILABLE:
        raise LookupError(f"Playwright not installed; skip {ats_type} board for {name}")

    scraped = await asyncio.to_thread(go_board_jobs, company)
    if scraped is not None and (
        scraped or ats_type not in _GO_EMPTY_TO_PYTHON or http_scrape_mode() == "go"
    ):
        log_event(f"go ats scrape returned {len(scraped)} job(s)", company=name)
        return scraped

    if ats_type in _GENERIC_ATS:
        return await fetch_generic_board(client, board_url, company)

    fetcher = _BOARD_FETCHERS.get(ats_type)
    if fetcher is not None:
        return await fetcher(client, board_url, company)

    raise UnsupportedAtsTypeError(ats_type)
