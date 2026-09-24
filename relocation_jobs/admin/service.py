from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from relocation_jobs.admin import repo as admin_repo
from relocation_jobs.users.applied import _timezone, local_day_utc_bounds
from relocation_jobs.users.entitlements import PLANS
from relocation_jobs.payments.types import ORDER_KIND_CREDITS, ORDER_KIND_FULL_ACCESS

from relocation_jobs.core.ats_constants import (
    DEFAULT_CONCURRENCY,
    KNOWN_ATS,
    MAX_CONCURRENCY,
)
from relocation_jobs.roles.service import default_keyword_lists
from relocation_jobs.core.location_tags import SUGGESTED_CITIES, all_country_labels, load_custom_cities, load_custom_countries
from relocation_jobs.core.paths import country_archive_filename, data_dir, supported_countries
from relocation_jobs.users.repo import user_count
from relocation_jobs.catalog.custom_countries import countries_use_redis
from relocation_jobs.catalog.repo import get_catalog_overview
from relocation_jobs.core.redis_client import ping_redis, redis_enabled
from relocation_jobs.fetch import repo as fetch_repo
from relocation_jobs.fetch.scheduler import (
    schedule_concurrency,
    schedule_enabled,
    schedule_interval_hours,
)
from relocation_jobs.panel.service import flatten_companies_for_stats
from relocation_jobs.panel.stats import compute_stats
from relocation_jobs.core.db import db_read


def get_system_config(
    *,
    scrape_enabled: bool,
    httpx_available: bool,
    company_fetch_enabled: bool | None = None,
) -> dict:
    custom = load_custom_cities()
    archives = [country_archive_filename(key) for key in sorted(supported_countries())]
    company_fetch = (
        scrape_enabled if company_fetch_enabled is None else company_fetch_enabled
    )
    return {
        "database": "postgres",
        "redis": "connected" if countries_use_redis() else ("configured" if redis_enabled() else "off"),
        "redis_ping": ping_redis() if redis_enabled() else False,
        "countries_store": "redis" if countries_use_redis() else "postgres",
        "data_dir": str(data_dir()),
        "scrape_enabled": scrape_enabled,
        "company_fetch_enabled": company_fetch,
        "allow_register": os.environ.get("PANEL_ALLOW_REGISTER", "").lower()
        in ("1", "true", "yes"),
        "httpx_available": httpx_available,
        "default_concurrency": DEFAULT_CONCURRENCY,
        "max_concurrency": MAX_CONCURRENCY,
        "include_keywords": default_keyword_lists()[0],
        "exclude_keywords": default_keyword_lists()[1],
        "known_ats_count": len(KNOWN_ATS),
        "known_ats_companies": sorted(KNOWN_ATS.keys()),
        "suggested_cities": {key: len(values) for key, values in SUGGESTED_CITIES.items()},
        "custom_cities": custom,
        "custom_countries": load_custom_countries(),
        "countries": [
            {"id": key, "label": label} for key, label in sorted(all_country_labels().items())
        ],
        "archives": archives,
    }


def get_worker_status(
    *,
    fetch_state: dict | None,
    scrape_enabled: bool,
    company_fetch_enabled: bool | None = None,
) -> dict:
    company_fetch = (
        scrape_enabled if company_fetch_enabled is None else company_fetch_enabled
    )
    return {
        "fetch": fetch_state or {"running": False},
        "last_country_run": fetch_repo.latest_finished_country_run(),
        "panel_scrape_enabled": scrape_enabled,
        "panel_company_fetch_enabled": company_fetch,
        "schedule_enabled": schedule_enabled(),
        "schedule_interval_hours": schedule_interval_hours(),
        "schedule_concurrency": schedule_concurrency(),
        "schedule_countries": (os.environ.get("FETCH_SCHEDULE_COUNTRIES") or "").strip(),
    }


def _fetched_today_bounds(
    timezone_name: str | None,
) -> tuple[str, str, str, str]:
    start_utc, end_utc = local_day_utc_bounds(timezone_name)
    tz = _timezone(timezone_name)
    start_date = datetime.fromisoformat(start_utc).astimezone(tz).date().isoformat()
    end_date = datetime.fromisoformat(end_utc).astimezone(tz).date().isoformat()
    return start_utc, end_utc, start_date, end_date


_FETCHED_TODAY_SQL = """
    (
      (LENGTH(j.fetched) > 10 AND j.fetched >= %s AND j.fetched < %s)
      OR
      (LENGTH(j.fetched) = 10 AND j.fetched >= %s AND j.fetched < %s)
    )
"""


def count_matching_jobs_fetched_today(
    *,
    timezone_name: str | None = None,
    country_key: str | None = None,
) -> int:
    start_utc, end_utc, start_date, end_date = _fetched_today_bounds(timezone_name)
    sql = f"""
        SELECT COUNT(*) AS n
        FROM matching_jobs j
        JOIN companies c ON c.id = j.company_id
        WHERE COALESCE(j.matches_default_filter, 1) = 1
          AND {_FETCHED_TODAY_SQL.strip()}
    """
    params: list = [start_utc, end_utc, start_date, end_date]
    if country_key and country_key != "all":
        sql += " AND c.country = %s"
        params.append(country_key)
    with db_read() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    return int((row or {}).get("n") or 0)


def compute_admin_panel_stats(
    *,
    user_id: int,
    country_key: str | None = None,
    location: str | None = None,
    ats_type: str | None = None,
    timezone_name: str | None = None,
) -> dict:
    companies, file_meta, fetch_problem_count = flatten_companies_for_stats(
        country_key,
        location=location,
        ats_type=ats_type,
        user_id=user_id,
    )
    stats = compute_stats(
        companies,
        file_meta,
        fetch_problem_count=fetch_problem_count,
        user_id=user_id,
        country_key=country_key,
        timezone_name=timezone_name,
    )
    stats["latest_fetch_new_jobs"] = count_matching_jobs_fetched_today(
        timezone_name=timezone_name,
        country_key=country_key,
    )
    return stats


def get_admin_overview(*, fetch_state: dict | None = None) -> dict:
    catalog = get_catalog_overview()
    return {
        "users": user_count(),
        "catalog": catalog["totals"],
        "fetch": fetch_state or {"running": False},
    }


def get_recently_fetched_jobs(
    *,
    limit: int = 30,
    timezone_name: str | None = None,
) -> list[dict]:
    start_utc, end_utc, start_date, end_date = _fetched_today_bounds(timezone_name)
    with db_read() as conn:
        rows = conn.execute(
            f"""
            SELECT j.title, j.url, j.fetched, j.visa_sponsorship,
                   c.name AS company_name, c.country
            FROM matching_jobs j
            JOIN companies c ON c.id = j.company_id
            WHERE COALESCE(j.matches_default_filter, 1) = 1
              AND {_FETCHED_TODAY_SQL.strip()}
            ORDER BY j.fetched DESC
            LIMIT %s
            """,
            (
                start_utc,
                end_utc,
                start_date,
                end_date,
                max(1, min(limit, 200)),
            ),
        ).fetchall()
    return [dict(r) for r in rows]


def get_admin_dashboard(
    *,
    fetch_state: dict | None = None,
    scrape_enabled: bool,
    company_fetch_enabled: bool | None = None,
) -> dict:
    return {
        "user_count": user_count(),
        "worker": get_worker_status(
            fetch_state=fetch_state,
            scrape_enabled=scrape_enabled,
            company_fetch_enabled=company_fetch_enabled,
        ),
        "panel_stats": None,
    }


_WORKSPACE_NOTE = (
    "Users with at least one mcp_applications row (company-workspace CV/cover-letter artifacts). "
    "Opening /company/… without saving an artifact is not stored."
)
_MCP_NOTE = (
    "Users with MCP quota consumed (users.mcp_quota_used > 0) or a stored MCP OAuth/API token. "
    "Read-only MCP use with no quota charge and no token is not stored."
)
_COHORT_WEEKS = 12
_PLAN_ORDER = ("free", "full", "grandfathered")


def _parse_ts(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_week(day: date) -> tuple[str, str]:
    iso = day.isocalendar()
    monday = day - timedelta(days=day.weekday())
    return monday.isoformat(), f"{iso.year}-W{iso.week:02d}"


def _signup_cohorts(users: list[dict], *, today: date) -> tuple[int, list[dict]]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    this_monday = _iso_week(today)[0]
    for user in users:
        parsed = _parse_ts(user.get("created_at"))
        if parsed is None:
            continue
        week_start, iso_week = _iso_week(parsed.date())
        counts[week_start] = counts.get(week_start, 0) + 1
        labels[week_start] = iso_week
    window = [
        (today - timedelta(days=today.weekday()) - timedelta(weeks=offset)).isoformat()
        for offset in range(_COHORT_WEEKS)
    ]
    keys = sorted(set(counts) | set(window), reverse=True)
    cohorts = [
        {
            "week_start": key,
            "iso_week": labels.get(key) or _iso_week(date.fromisoformat(key))[1],
            "signups": counts.get(key, 0),
        }
        for key in keys
    ]
    return counts.get(this_monday, 0), cohorts


def _plan_counts(users: list[dict]) -> dict[str, int]:
    by_plan = {plan: 0 for plan in _PLAN_ORDER}
    for user in users:
        plan = (user.get("plan") or "free").strip().lower() or "free"
        if plan not in PLANS:
            plan = "free"
        by_plan[plan] = by_plan.get(plan, 0) + 1
    return by_plan


def _step(*, key: str, label: str, count: int | None, available: bool, definition: str) -> dict:
    return {
        "key": key,
        "label": label,
        "available": available,
        "count": count,
        "definition": definition,
    }


def _event(*, key: str, label: str, row: dict | None, available: bool = True, gap: str = "") -> dict:
    payload = {
        "key": key,
        "label": label,
        "available": available,
        "at": None,
        "user_id": None,
        "username": None,
        "gap": gap,
    }
    if not available or not row:
        return payload
    payload["at"] = row.get("at") or None
    payload["user_id"] = row.get("user_id")
    payload["username"] = row.get("username")
    return payload


def _latest_mcp_event() -> dict | None:
    latest = None
    latest_ts = None
    for row in admin_repo.mcp_activity_rows():
        parsed = _parse_ts(row.get("at"))
        if parsed is None:
            continue
        if latest_ts is None or parsed > latest_ts:
            latest = row
            latest_ts = parsed
    return latest


def get_activation_metrics() -> dict:
    users = admin_repo.list_users_for_activation()
    today = datetime.now(timezone.utc).date()
    signups_this_week, cohorts = _signup_cohorts(users, today=today)
    this_monday, this_label = _iso_week(today)
    return {
        "total_users": len(users),
        "signups_this_week": signups_this_week,
        "current_week": {"week_start": this_monday, "iso_week": this_label},
        "plans": _plan_counts(users),
        "signup_cohorts": cohorts,
        "activation": [
            _step(
                key="subsequent_login",
                label="Subsequent login",
                count=admin_repo.count_users_with_subsequent_login(),
                available=True,
                definition=(
                    "Users whose last_login_at is after created_at "
                    "(they signed in again after signup)."
                ),
            ),
            _step(
                key="job_track",
                label="Job track",
                count=admin_repo.count_users_with_job_track(),
                available=True,
                definition="Users with at least one job_tracking row.",
            ),
            _step(
                key="workspace",
                label="Workspace",
                count=admin_repo.count_users_with_workspace(),
                available=True,
                definition=_WORKSPACE_NOTE,
            ),
            _step(
                key="mcp",
                label="MCP",
                count=admin_repo.count_users_with_mcp(),
                available=True,
                definition=_MCP_NOTE,
            ),
            _step(
                key="credit_purchase",
                label="Credit purchase",
                count=admin_repo.count_users_with_paid_order(ORDER_KIND_CREDITS),
                available=True,
                definition="Users with at least one paid credit_orders row (kind=credits).",
            ),
            _step(
                key="full_purchase",
                label="Full purchase",
                count=admin_repo.count_users_with_paid_order(ORDER_KIND_FULL_ACCESS),
                available=True,
                definition="Users with at least one paid credit_orders row (kind=full_access).",
            ),
        ],
        "latest_activity": [
            _event(key="signup", label="Latest signup", row=admin_repo.latest_signup()),
            _event(
                key="subsequent_login",
                label="Latest subsequent login",
                row=admin_repo.latest_subsequent_login(),
            ),
            _event(key="job_track", label="Latest job track", row=admin_repo.latest_job_track()),
            _event(key="workspace", label="Latest workspace artifact", row=admin_repo.latest_workspace()),
            _event(key="mcp", label="Latest MCP signal", row=_latest_mcp_event()),
            _event(
                key="credit_purchase",
                label="Latest credit purchase",
                row=admin_repo.latest_paid_order(ORDER_KIND_CREDITS),
            ),
            _event(
                key="full_purchase",
                label="Latest Full purchase",
                row=admin_repo.latest_paid_order(ORDER_KIND_FULL_ACCESS),
            ),
        ],
    }
