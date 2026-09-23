from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from relocation_jobs.core.job_identity import job_idempotency_key
from relocation_jobs.core.scrape_cancel import FetchCancelled, raise_if_cancelled
from relocation_jobs.fetch.log import log_event
from relocation_jobs.fetch.types import is_infra_fetch_error
from relocation_jobs.scrape.aggregator_sync import (
    aggregator_success_line,
    is_aggregator_ats,
    sync_aggregator_board,
)
from relocation_jobs.scrape.filter import filter_relevant_jobs
from relocation_jobs.scrape.merge import merge_matching_jobs, now_iso
from relocation_jobs.scrape.review import build_review_payload, review_filtered_jobs
from relocation_jobs.shared.predicates import any_of


@dataclass(frozen=True)
class _ScrapeLineContext:
    job_count: int
    sponsored: int
    preserved: int
    new_count: int
    stale_kept: int


_SCRAPE_SUMMARY_PARTS: tuple[Callable[[_ScrapeLineContext], str | None], ...] = (
    lambda ctx: f"{ctx.sponsored} with visa/relocation support" if ctx.sponsored else None,
    lambda ctx: f"{ctx.preserved} preserved" if ctx.preserved else None,
    lambda ctx: f"{ctx.new_count} new" if ctx.new_count else None,
    lambda ctx: f"{ctx.stale_kept} kept from cache" if ctx.stale_kept else None,
)

_SKIP_POST_SCRAPE_ENRICH: tuple[Callable[[Callable | None], bool], ...] = (
    lambda board: board is None,
)

_MARK_FETCH_FAILED: tuple[Callable[[BaseException], bool], ...] = (
    lambda exc: not is_infra_fetch_error(str(exc)),
)


def _today() -> str:
    return date.today().isoformat()


def _company_line(company: dict, index: int, total: int) -> str:
    name = company.get("name") or ""
    city = company.get("city", "?")
    return f"[{index}/{total}] {name} ({city})"


def _call_sync_board(sync_board: Callable | None) -> None:
    if sync_board:
        sync_board()


def _sponsored_count(jobs: list[dict]) -> int:
    return sum(1 for job in jobs if job.get("visa_sponsorship") is True)


def _mark_fetch_ok(company: dict) -> None:
    company.pop("fetch_problem", None)
    company.pop("fetch_problem_date", None)
    company["fetch_ok"] = True
    company["fetch_ok_date"] = _today()


def _mark_fetch_failed(company: dict) -> None:
    company["fetch_problem"] = True
    company["fetch_problem_date"] = _today()
    company["fetch_ok"] = False
    company.pop("fetch_ok_date", None)


def _slim_new_jobs(jobs: list[dict]) -> list[dict]:
    out: list[dict] = []
    for job in jobs:
        url = (job.get("url") or "").strip()
        title = (job.get("title") or "").strip() or url
        if not url:
            continue
        out.append({"title": title, "url": url})
    return out


def _scrape_success_line(
    prefix: str,
    jobs: list[dict],
    *,
    preserved: int,
    new_count: int,
    stale_kept: int,
) -> str:
    ctx = _ScrapeLineContext(
        job_count=len(jobs),
        sponsored=_sponsored_count(jobs),
        preserved=preserved,
        new_count=new_count,
        stale_kept=stale_kept,
    )
    parts = [f"{ctx.job_count} matching job(s)"]
    parts.extend(part for rule in _SCRAPE_SUMMARY_PARTS if (part := rule(ctx)))
    return f"{prefix} — {', '.join(parts)}"


def _emit_review(
    *,
    review_mode: bool,
    on_review: Callable | None,
    raw: list[dict],
    included: list[dict],
    name: str,
) -> None:
    if not review_mode or not on_review:
        return
    filtered_out = review_filtered_jobs(raw, included)
    on_review(build_review_payload(included=included, filtered=filtered_out))
    log_event(
        f"review: {len(included)} included, {len(filtered_out)} filtered",
        company=name,
    )


async def _filter_board_listings(
    client,
    company: dict,
    *,
    fetch_board: Callable,
) -> tuple[list[dict], list[dict]]:
    name = company.get("name") or ""
    raw = await fetch_board(client, company)
    log_event(f"board returned {len(raw)} raw job(s)", company=name)
    title_matched = filter_relevant_jobs(raw, True)
    log_event(f"relevance filter: {len(raw)} → {len(title_matched)}", company=name)
    return title_matched, raw


async def _maybe_enrich_scraped_board(
    client,
    jobs: list[dict],
    company: dict,
    *,
    enrich_board: Callable | None,
    enrich_concurrency: int,
) -> list[dict]:
    if any_of(enrich_board, _SKIP_POST_SCRAPE_ENRICH):
        return jobs
    return await enrich_board(
        client, jobs, company,
        only_missing=True,
        concurrency=enrich_concurrency,
    )


async def scrape_company_board(
    client,
    company: dict,
    prefix: str,
    *,
    fetch_board: Callable,
    enrich_board: Callable | None,
    enrich_concurrency: int,
    catalog_country: str,
    sync_board: Callable,
    review_mode: bool = False,
    on_review: Callable | None = None,
    on_company_result: Callable | None = None,
) -> tuple[str, int]:
    raise_if_cancelled()
    name = company.get("name") or ""
    ats = (company.get("ats_type") or "generic").strip()
    log_event(f"scraping board ats={ats}", company=name)
    if is_aggregator_ats(ats):
        return await _scrape_aggregator_board(
            client,
            company,
            prefix,
            fetch_board=fetch_board,
            catalog_country=catalog_country,
            sync_board=sync_board,
            review_mode=review_mode,
            on_review=on_review,
            on_company_result=on_company_result,
        )
    existing = list(company.get("matching_jobs") or [])
    scraped, raw = await _filter_board_listings(
        client, company,
        fetch_board=fetch_board,
    )
    raise_if_cancelled()
    _emit_review(
        review_mode=review_mode,
        on_review=on_review,
        raw=raw,
        included=scraped,
        name=name,
    )
    known = {job_idempotency_key(j.get("url", "")) for j in existing}
    scraped.extend(j for j in raw if job_idempotency_key(j.get("url", "")) in known)
    jobs, preserved, new_count, stale_kept, new_jobs = merge_matching_jobs(existing, scraped)
    if on_company_result and new_count > 0:
        on_company_result(name, new_count, _slim_new_jobs(new_jobs))
    jobs = await _maybe_enrich_scraped_board(
        client, jobs, company,
        enrich_board=enrich_board,
        enrich_concurrency=enrich_concurrency,
    )
    company["matching_jobs"] = jobs
    company["updated"] = now_iso()
    _mark_fetch_ok(company)
    _call_sync_board(sync_board)
    return _scrape_success_line(
        prefix, jobs,
        preserved=preserved,
        new_count=new_count,
        stale_kept=stale_kept,
    ), new_count


async def _scrape_aggregator_board(
    client,
    company: dict,
    prefix: str,
    *,
    fetch_board: Callable,
    catalog_country: str,
    sync_board: Callable,
    review_mode: bool = False,
    on_review: Callable | None = None,
    on_company_result: Callable | None = None,
) -> tuple[str, int]:
    name = company.get("name") or ""
    raw = await fetch_board(client, company)
    log_event(f"board returned {len(raw)} raw job(s)", company=name)
    raise_if_cancelled()
    matched = filter_relevant_jobs(raw, True)
    employers, job_total = sync_aggregator_board(
        catalog_country,
        company,
        raw,
        relevant_only=True,
    )
    _emit_review(
        review_mode=review_mode,
        on_review=on_review,
        raw=raw,
        included=matched,
        name=name,
    )
    if on_company_result and job_total > 0:
        on_company_result(name, job_total, _slim_new_jobs(matched))
    company["matching_jobs"] = []
    company["updated"] = now_iso()
    _mark_fetch_ok(company)
    _call_sync_board(sync_board)
    return aggregator_success_line(prefix, employers, job_total), job_total


async def process_company(
    client,
    company: dict,
    index: int,
    total: int,
    *,
    fetch_board: Callable,
    enrich_board: Callable | None = None,
    sync_board: Callable | None = None,
    enrich_concurrency: int = 8,
    catalog_country: str = "",
    review_mode: bool = False,
    on_review: Callable | None = None,
    on_company_result: Callable | None = None,
) -> tuple[str, int]:
    company["updated"] = now_iso()
    prefix = _company_line(company, index, total)
    try:
        return await scrape_company_board(
            client, company, prefix,
            fetch_board=fetch_board,
            enrich_board=enrich_board,
            enrich_concurrency=enrich_concurrency,
            catalog_country=catalog_country,
            sync_board=sync_board,
            review_mode=review_mode,
            on_review=on_review,
            on_company_result=on_company_result,
        )
    except FetchCancelled:
        raise
    except Exception as exc:
        if any_of(exc, _MARK_FETCH_FAILED):
            _mark_fetch_failed(company)
        _call_sync_board(sync_board)
        return f"{prefix} — Error: {exc}", 0
