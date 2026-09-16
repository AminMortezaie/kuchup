from __future__ import annotations

from collections.abc import Callable

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog
from relocation_jobs.core.ats_constants import MAX_CONCURRENCY
from relocation_jobs.core.scrape_cancel import FetchCancelled
from relocation_jobs.fetch import service as fetch_service
from relocation_jobs.scrape.board import fetch_ats_board
from relocation_jobs.scrape.company import process_company
from relocation_jobs.scrape.enrich import enrich_jobs


async def fetch_and_persist_company(
    client,
    country_key: str,
    company_name: str,
    *,
    index: int = 1,
    total: int = 1,
    fetch_board: Callable | None = None,
    enrich_concurrency: int = MAX_CONCURRENCY,
    fetch_run_id: int | None = None,
    review_mode: bool = False,
    on_review: Callable | None = None,
    on_company_result: Callable | None = None,
) -> tuple[str, int]:
    company = get_company(country_key, company_name)
    if company is None:
        raise LookupError(f"Company not found: {company_name}")

    def persist_board() -> None:
        sync_company_board_to_catalog(country_key, company)

    board_fetch = fetch_board or fetch_ats_board

    async def _fetch_board(proc_client, proc_company: dict, **kwargs) -> list[dict]:
        return await board_fetch(
            proc_client,
            proc_company,
            sync_board=persist_board,
            **kwargs,
        )

    attempt_id = fetch_service.start_company_attempt(
        company, country_key=country_key, fetch_run_id=fetch_run_id,
    )
    try:
        msg, new_count = await process_company(
            client,
            company,
            index,
            total,
            fetch_board=_fetch_board,
            enrich_board=enrich_jobs,
            sync_board=persist_board,
            enrich_concurrency=enrich_concurrency,
            catalog_country=country_key,
            review_mode=review_mode,
            on_review=on_review,
            on_company_result=on_company_result,
        )
    except FetchCancelled:
        fetch_service.finish_cancelled_attempt(attempt_id)
        raise
    return fetch_service.finish_company_attempt(attempt_id, company, msg, new_count)
