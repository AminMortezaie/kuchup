from __future__ import annotations

BOARD_ROLES_PAGE_SIZE = 3
ROLE_BUCKETS = ("jobs", "rejected_jobs", "not_for_me_jobs")
_MORE_SUFFIX = "_more"


def roles_more_key(bucket: str) -> str:
    return f"{bucket}{_MORE_SUFFIX}"


def truncate_board_company_roles(
    company: dict,
    *,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> dict:
    row = dict(company)
    page = max(1, int(limit))
    for bucket in ROLE_BUCKETS:
        items = list(row.get(bucket) or [])
        row[roles_more_key(bucket)] = max(0, len(items) - page)
        if len(items) > page:
            row[bucket] = items[:page]
    return row


def truncate_board_companies(
    companies: list[dict],
    *,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> list[dict]:
    return [truncate_board_company_roles(company, limit=limit) for company in companies]


def slice_role_bucket(
    items: list[dict],
    *,
    offset: int,
    limit: int = BOARD_ROLES_PAGE_SIZE,
) -> tuple[list[dict], int, int]:
    total = len(items)
    start = max(0, int(offset))
    page = max(1, int(limit))
    chunk = items[start:start + page]
    remaining = max(0, total - start - len(chunk))
    return chunk, total, remaining
