from __future__ import annotations

BOARD_ROLES_PAGE_SIZE = 3


def truncate_board_company_roles(
    company: dict,
    *,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> dict:
    row = dict(company)
    page = max(1, int(limit))
    items = list(row.get("jobs") or [])
    row["jobs_more"] = max(0, len(items) - page)
    if len(items) > page:
        row["jobs"] = items[:page]
    return row


def truncate_board_companies(
    companies: list[dict],
    *,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> list[dict]:
    return [truncate_board_company_roles(company, limit=limit) for company in companies]


def slice_open_roles(
    items: list[dict],
    *,
    offset: int,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> tuple[list[dict], int]:
    start = max(0, int(offset))
    page = max(1, int(limit))
    chunk = items[start:start + page]
    remaining = max(0, len(items) - start - len(chunk))
    return chunk, remaining
