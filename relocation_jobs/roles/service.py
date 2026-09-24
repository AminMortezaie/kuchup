from __future__ import annotations

import json

from relocation_jobs.core.ats_constants import EXCLUDE_KEYWORDS, INCLUDE_KEYWORDS
from relocation_jobs.core.job_identity import job_idempotency_key_for_job
from relocation_jobs.panel.tracking import job_dict
from relocation_jobs.roles import repo
from relocation_jobs.scrape.relevance import hidden_by_active_excludes, is_relevant
from relocation_jobs.users.repo import load_job_tracking

_cached_keywords: tuple[list[str], list[str]] | None = None


def clear_keyword_cache() -> None:
    global _cached_keywords
    _cached_keywords = None


def job_is_default_match(job: dict) -> bool:
    if "matches_default_filter" not in job:
        return True
    raw = job.get("matches_default_filter")
    if isinstance(raw, bool):
        return raw
    if raw is None or raw == "":
        return True
    try:
        return int(raw) != 0
    except (TypeError, ValueError):
        return True


def default_keyword_lists() -> tuple[list[str], list[str]]:
    global _cached_keywords
    if _cached_keywords is not None:
        return _cached_keywords
    try:
        tags = repo.list_role_filter_tags()
    except Exception:
        return list(INCLUDE_KEYWORDS), list(EXCLUDE_KEYWORDS)
    if not tags:
        return list(INCLUDE_KEYWORDS), list(EXCLUDE_KEYWORDS)
    includes = [row["keyword"] for row in tags if row["kind"] == "include"]
    excludes = [row["keyword"] for row in tags if row["kind"] == "exclude"]
    _cached_keywords = (includes, excludes)
    return _cached_keywords


def title_matches_default(title: str) -> bool:
    includes, excludes = default_keyword_lists()
    return is_relevant(title, include=includes, exclude=excludes)


def annotate_listings(jobs: list[dict]) -> list[dict]:
    for job in jobs:
        matched = title_matches_default((job.get("title") or "").strip())
        job["matches_default_filter"] = 1 if matched else 0
        if not matched:
            job.pop("description_text", None)
            job.pop("visa_sponsorship", None)
    return jobs


def _disabled_exclude_keywords(user_id: int) -> list[str]:
    disabled_ids = set(repo.list_disabled_tag_ids(user_id))
    if not disabled_ids:
        return []
    tags = repo.list_role_filter_tags()
    return [
        row["keyword"]
        for row in tags
        if row["kind"] == "exclude" and int(row["id"]) in disabled_ids
    ]


def title_unhidden(title: str, disabled_excludes: list[str]) -> bool:
    if not disabled_excludes:
        return False
    folded = (title or "").lower()
    if not any(keyword in folded for keyword in disabled_excludes):
        return False
    _, excludes = default_keyword_lists()
    disabled = set(disabled_excludes)
    active = [keyword for keyword in excludes if keyword not in disabled]
    return not hidden_by_active_excludes(title, active)


def list_preferences(user_id: int) -> list[dict]:
    disabled = set(repo.list_disabled_tag_ids(user_id))
    out: list[dict] = []
    for row in repo.list_role_filter_tags():
        tag_id = int(row["id"])
        out.append({
            "id": tag_id,
            "keyword": row["keyword"],
            "kind": row["kind"],
            "is_default": bool(int(row.get("is_default") or 0)),
            "enabled": tag_id not in disabled,
        })
    return out


def set_tag_enabled(user_id: int, tag_id: int, enabled: bool) -> dict:
    tag = repo.get_role_filter_tag(tag_id)
    if tag is None:
        raise LookupError("Unknown role filter tag")
    if enabled:
        repo.delete_user_tag_pref(user_id, tag_id)
    else:
        repo.upsert_disabled_tag_pref(user_id, tag_id)
    saved = next(item for item in list_preferences(user_id) if item["id"] == tag_id)
    return saved


def _clean_keyword(keyword: str, kind: str) -> tuple[str, str]:
    text = keyword if isinstance(keyword, str) else ""
    if text.strip() == "":
        raise ValueError("keyword is required")
    role_kind = (kind or "").strip().lower()
    if role_kind not in ("include", "exclude"):
        raise ValueError("kind must be include or exclude")
    return text, role_kind


def add_tag(keyword: str, kind: str) -> dict:
    text, role_kind = _clean_keyword(keyword, kind)
    if repo.find_role_filter_tag(role_kind, text) is not None:
        raise ValueError("tag already exists")
    saved = repo.insert_role_filter_tag(text, role_kind)
    clear_keyword_cache()
    return {
        "id": int(saved["id"]),
        "keyword": saved["keyword"],
        "kind": saved["kind"],
        "is_default": True,
        "enabled": True,
    }


def edit_tag(tag_id: int, keyword: str, kind: str) -> dict:
    text, role_kind = _clean_keyword(keyword, kind)
    existing = repo.find_role_filter_tag(role_kind, text)
    if existing is not None and int(existing["id"]) != tag_id:
        raise ValueError("tag already exists")
    saved = repo.update_role_filter_tag(tag_id, text, role_kind)
    if saved is None:
        raise LookupError("Unknown role filter tag")
    clear_keyword_cache()
    return {
        "id": int(saved["id"]),
        "keyword": saved["keyword"],
        "kind": saved["kind"],
        "is_default": bool(int(saved.get("is_default") or 0)),
    }


def _locations_from_row(row: dict) -> dict:
    job: dict = {}
    location = (row.get("location") or "").strip()
    if location:
        job["location"] = location
    raw = row.get("locations_json")
    if raw and raw != "[]":
        try:
            locs = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            locs = None
        if isinstance(locs, list) and locs:
            job["locations"] = locs
    return job


def mix_unhidden_roles(
    user_id: int | None,
    companies: list[dict],
    *,
    visa_only: bool = False,
) -> list[dict]:
    if not user_id or visa_only or not companies:
        return companies
    disabled = _disabled_exclude_keywords(user_id)
    if not disabled:
        return companies
    keys = [
        ((company.get("country") or "").strip().lower(), (company.get("name") or "").strip())
        for company in companies
    ]
    rows = repo.list_open_nondefault_jobs(keys)
    if not rows:
        return companies
    tracking = load_job_tracking(user_id)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (
            (row.get("country") or "").strip().lower(),
            (row.get("company_name") or "").strip().lower(),
        )
        grouped.setdefault(key, []).append(row)
    for company in companies:
        key = (
            (company.get("country") or "").strip().lower(),
            (company.get("name") or "").strip().lower(),
        )
        extras = grouped.get(key) or []
        if not extras:
            continue
        jobs = list(company.get("jobs") or [])
        seen = {
            (job.get("idempotency_key") or "").strip() or (job.get("url") or "").strip()
            for job in jobs
        }
        added = _extra_job_entries(
            extras,
            company=company,
            disabled=disabled,
            seen=seen,
            tracking=tracking,
        )
        if not added:
            continue
        company["jobs"] = jobs + added
        company["job_count"] = len(company["jobs"])
    return companies


def _extra_job_entries(
    extras: list[dict],
    *,
    company: dict,
    disabled: list[str],
    seen: set[str],
    tracking: dict,
) -> list[dict]:
    added: list[dict] = []
    country_key = (company.get("country") or "").strip().lower()
    company_name = (company.get("name") or "").strip()
    for row in extras:
        title = (row.get("title") or "").strip()
        if not title_unhidden(title, disabled):
            continue
        job = {
            "title": title,
            "url": (row.get("url") or "").strip(),
            "idempotency_key": (row.get("idempotency_key") or "").strip(),
            "fetched": row.get("fetched") or "",
            "last_seen": row.get("last_seen") or "",
            "visa_sponsorship": None,
            "closed_at": "",
            "matches_default_filter": 0,
            **_locations_from_row(row),
        }
        if not job["idempotency_key"]:
            job["idempotency_key"] = job_idempotency_key_for_job(job)
        identity = job["idempotency_key"] or job["url"]
        if not job["url"] or identity in seen:
            continue
        seen.add(identity)
        entry = job_dict(
            job,
            company_name=company_name,
            company=company,
            country_key=country_key,
            country_label=company.get("country_label") or "",
            job_tracking=tracking,
        )
        entry["preference_extra"] = True
        entry["matches_default_filter"] = False
        added.append(entry)
    return added
