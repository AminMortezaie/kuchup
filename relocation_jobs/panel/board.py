from __future__ import annotations

from relocation_jobs.opportunities.types import BoardOpportunityScope
from relocation_jobs.panel.service import flatten_companies_page
from relocation_jobs.panel.types import FlattenFilters
from relocation_jobs.shared.board_contract import CATALOG_KIND_REMOTE

DEFAULT_BOARD_PAGE_SIZE = 25
MAX_BOARD_PAGE_SIZE = 100


def load_catalog_board_page(
    country_key: str | None,
    *,
    ats_type: str | None,
    location: str | None,
    user_id: int | None,
    visible_offset: int,
    limit: int,
    search: str | None = None,
    panel_flags: dict | None = None,
    count_total: bool = False,
    sort: str | None = "newest",
    catalog_kind: str = "relocation",
    opportunity_scope: BoardOpportunityScope | None = None,
) -> tuple[list[dict], list[dict], int, int | None, bool]:
    flags = panel_flags or {}
    opportunity_company_keys = None
    opportunity_country_keys = None
    # Remote catalog is not scoped by relocation target_countries (Germany defaults
    # would otherwise empty the Remote board). Cap/plan still surface in meta.
    apply_opportunity_scope = (
        opportunity_scope is not None
        and not opportunity_scope.bypass
        and catalog_kind != CATALOG_KIND_REMOTE
    )
    if apply_opportunity_scope:
        opportunity_company_keys = opportunity_scope.company_keys
        opportunity_country_keys = opportunity_scope.country_keys
    filters = FlattenFilters.from_kwargs(
        country_key=country_key,
        user_id=user_id,
        location=location,
        ats_type=ats_type,
        catalog_kind=catalog_kind,
        opportunity_company_keys=opportunity_company_keys,
        opportunity_country_keys=opportunity_country_keys,
        visa_only=flags.get("visa_only", False),
        hide_applied=flags.get("hide_applied", False),
        hide_empty=flags.get("hide_empty", False),
        not_applied_only=flags.get("not_applied_only", False),
        fetch_ok_only=flags.get("fetch_ok_only", False),
        fetch_problem_only=flags.get("fetch_problem_only", False),
        hide_position_applied=flags.get("hide_position_applied", False),
        hide_position_rejected=flags.get("hide_position_rejected", False),
        position_applied_only=flags.get("position_applied_only", False),
        position_rejected_only=flags.get("position_rejected_only", False),
        position_looking_to_apply_only=flags.get("position_looking_to_apply_only", False),
    )
    return flatten_companies_page(
        filters,
        visible_offset=visible_offset,
        limit=limit,
        search=search,
        count_total=count_total,
        sort=sort,
    )
