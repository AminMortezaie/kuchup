from __future__ import annotations

import math

from flask import request

from relocation_jobs.broadcast.service import apply_capacity_to_board_page, capacity_meta_for_user
from relocation_jobs.opportunities.service import board_scope_meta, resolve_board_opportunity_scope
from relocation_jobs.opportunities.types import BoardOpportunityScope
from relocation_jobs.panel.board import (
    DEFAULT_BOARD_PAGE_SIZE,
    MAX_BOARD_PAGE_SIZE,
    load_catalog_board_page,
)
from relocation_jobs.panel.flatten_rules import company_has_open_roles
from relocation_jobs.panel.stats import compute_user_board_stats, resolve_new_jobs_count
from relocation_jobs.shared.board_contract import (
    CATALOG_KIND_REMOTE,
    CATALOG_KIND_RELOCATION,
    CATALOG_KINDS,
    is_remote_country_key,
)
from relocation_jobs.web.query import query_bool, query_flags

_PANEL_FLAG_KEYS = (
    "hide_applied",
    "hide_empty",
    "not_applied_only",
    "hide_position_applied",
    "hide_position_rejected",
    "position_applied_only",
    "position_rejected_only",
    "position_looking_to_apply_only",
    "fetch_ok_only",
    "fetch_problem_only",
)


def parse_board_page_args() -> tuple[int, int, str, str | None]:
    search = (request.args.get("q") or "").strip() or None
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    page_size = request.args.get("page_size", DEFAULT_BOARD_PAGE_SIZE, type=int) or DEFAULT_BOARD_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_BOARD_PAGE_SIZE))
    sort = (request.args.get("sort") or "newest").strip().lower()
    if sort not in ("newest", "name"):
        sort = "newest"
    return page, page_size, sort, search


def panel_flags_for_kind(flags: dict, catalog_kind: str) -> dict:
    visa_only = False if catalog_kind == CATALOG_KIND_REMOTE else flags["visa_only"]
    return {"visa_only": visa_only, **{key: flags[key] for key in _PANEL_FLAG_KEYS}}


def catalog_kind_for_mutation(job_country: str | None) -> str:
    raw = (request.args.get("catalog_kind") or "").strip().lower()
    if raw in CATALOG_KINDS:
        return raw
    flags = query_flags()
    if is_remote_country_key(flags["country_key"]) or is_remote_country_key(job_country):
        return CATALOG_KIND_REMOTE
    return CATALOG_KIND_RELOCATION


def _filter_empty_then_slice(
    companies: list[dict],
    panel_flags: dict,
    visible_offset: int,
    page_size: int,
) -> tuple[list[dict], int, bool]:
    rejected_only = bool(panel_flags.get("position_rejected_only"))
    visible = [
        company
        for company in companies
        if company_has_open_roles(
            company.get("jobs"),
            company.get("rejected_jobs"),
            rejected_only=rejected_only,
        )
    ]
    total_visible = len(visible)
    has_more = visible_offset + page_size < total_visible
    return visible[visible_offset:visible_offset + page_size], total_visible, has_more


def _board_payload_at_page(
    user_id: int,
    *,
    catalog_kind: str,
    flags: dict,
    page: int,
    page_size: int,
    sort: str,
    search: str | None,
    count_total: bool | None,
) -> dict:
    is_remote = catalog_kind == CATALOG_KIND_REMOTE
    opportunity_scope = resolve_board_opportunity_scope(user_id)
    panel_flags = panel_flags_for_kind(flags, catalog_kind)
    requested_hide_empty = panel_flags["hide_empty"]
    defer_empty = (
        not is_remote
        and requested_hide_empty
        and opportunity_scope.plan == "free"
        and not opportunity_scope.bypass
    )
    if defer_empty:
        panel_flags["hide_empty"] = False
    visible_offset = (page - 1) * page_size
    if count_total is None:
        count_total = True if defer_empty else (page == 1)
    companies, file_meta, fetch_problem_count, total_visible, has_more = load_catalog_board_page(
        flags["country_key"],
        ats_type=flags["ats_type"],
        location=flags["location"],
        user_id=user_id,
        visible_offset=0 if defer_empty else visible_offset,
        limit=None if defer_empty else page_size,
        search=search,
        panel_flags=panel_flags,
        count_total=count_total,
        sort=sort,
        catalog_kind=catalog_kind,
        opportunity_scope=opportunity_scope,
    )
    capacity_meta = {}
    if not is_remote:
        companies = apply_capacity_to_board_page(user_id, companies)
        capacity_meta = capacity_meta_for_user(user_id).as_dict()
    if defer_empty:
        companies, total_visible, has_more = _filter_empty_then_slice(
            companies, panel_flags, visible_offset, page_size,
        )
    latest_fetch_new_jobs = resolve_new_jobs_count(
        user_id=user_id,
        country_key=flags["country_key"],
        timezone_name=flags["timezone_name"],
        file_meta=file_meta,
    )
    return _board_json(
        companies,
        flags=flags,
        catalog_kind=catalog_kind,
        fetch_problem_count=fetch_problem_count,
        latest_fetch_new_jobs=latest_fetch_new_jobs,
        page=page,
        page_size=page_size,
        total_visible=total_visible,
        has_more=has_more,
        sort=sort,
        opportunity_scope=opportunity_scope,
        capacity_meta=capacity_meta,
        user_id=user_id,
    )


def _board_json(
    companies: list[dict],
    *,
    flags: dict,
    catalog_kind: str,
    fetch_problem_count: int,
    latest_fetch_new_jobs: int,
    page: int,
    page_size: int,
    total_visible: int | None,
    has_more: bool,
    sort: str,
    opportunity_scope: BoardOpportunityScope,
    capacity_meta: dict,
    user_id: int,
) -> dict:
    total_pages = None
    if total_visible is not None:
        total_pages = max(1, math.ceil(total_visible / page_size))
    return {
        "companies": companies,
        "meta": {
            "country": request.args.get("country", "all"),
            "ats_type": flags["ats_type"],
            "location": flags["location"],
            "catalog_kind": catalog_kind,
            "fetch_problem_total": fetch_problem_count,
            "latest_fetch_new_jobs": latest_fetch_new_jobs,
            "page": page,
            "page_size": page_size,
            "total_companies": total_visible,
            "total_pages": total_pages,
            "has_more": has_more,
            "sort": sort,
            **board_scope_meta(opportunity_scope),
            **capacity_meta,
        },
        "user_stats": compute_user_board_stats(
            user_id=user_id,
            country_key=flags["country_key"],
            timezone_name=flags["timezone_name"],
            latest_fetch_new_jobs=latest_fetch_new_jobs,
        ),
    }


def build_board_payload(
    user_id: int,
    *,
    catalog_kind: str = CATALOG_KIND_RELOCATION,
    count_total: bool | None = None,
    clamp_empty_page: bool = False,
) -> dict:
    flags = query_flags()
    page, page_size, sort, search = parse_board_page_args()
    payload = _board_payload_at_page(
        user_id,
        catalog_kind=catalog_kind,
        flags=flags,
        page=page,
        page_size=page_size,
        sort=sort,
        search=search,
        count_total=count_total,
    )
    total_pages = payload["meta"].get("total_pages")
    if clamp_empty_page and total_pages and page > total_pages:
        payload = _board_payload_at_page(
            user_id,
            catalog_kind=catalog_kind,
            flags=flags,
            page=total_pages,
            page_size=page_size,
            sort=sort,
            search=search,
            count_total=True,
        )
    return payload


def mutation_board_fields(user_id: int, *, job_country: str | None) -> dict:
    if not query_bool("include_board"):
        return {}
    snapshot = build_board_payload(
        user_id,
        catalog_kind=catalog_kind_for_mutation(job_country),
        count_total=True,
        clamp_empty_page=True,
    )
    return {
        "board": {"companies": snapshot["companies"], "meta": snapshot["meta"]},
        "user_stats": snapshot["user_stats"],
    }
