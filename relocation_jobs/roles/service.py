from __future__ import annotations

from relocation_jobs.core.job_identity import job_idempotency_key_for_job
from relocation_jobs.roles import repo
from relocation_jobs.users.repo import load_job_tracking


def default_keyword_lists() -> tuple[list[str], list[str]]:
    tags = repo.list_role_filter_tags()
    includes = [row["keyword"] for row in tags if row["kind"] == "include"]
    excludes = [row["keyword"] for row in tags if row["kind"] == "exclude"]
    return includes, excludes


def annotate_listings(jobs: list[dict], includes: list[str], excludes: list[str]) -> list[dict]:
    from relocation_jobs.scrape.relevance import is_relevant

    for job in jobs:
        matched = is_relevant((job.get("title") or "").strip(), include=includes, exclude=excludes)
        job["matches_default_filter"] = 1 if matched else 0
        if not matched:
            job.pop("description_text", None)
            job.pop("visa_sponsorship", None)
    return jobs


def _unhide_exclude_state(user_id: int) -> tuple[list[str], list[str]] | None:
    disabled_ids = set(repo.list_disabled_tag_ids(user_id))
    if not disabled_ids:
        return None
    tags = repo.list_role_filter_tags()
    disabled = [
        row["keyword"]
        for row in tags
        if row["kind"] == "exclude" and int(row["id"]) in disabled_ids
    ]
    if not disabled:
        return None
    disabled_set = set(disabled)
    active = [
        row["keyword"]
        for row in tags
        if row["kind"] == "exclude" and row["keyword"] not in disabled_set
    ]
    return disabled, active


def title_unhidden(title: str, disabled_excludes: list[str], active_excludes: list[str]) -> bool:
    if not disabled_excludes:
        return False
    folded = (title or "").lower()
    if not any(keyword in folded for keyword in disabled_excludes):
        return False
    from relocation_jobs.scrape.relevance import hidden_by_active_excludes

    return not hidden_by_active_excludes(title, active_excludes)


def list_preferences(user_id: int) -> list[dict]:
    disabled = set(repo.list_disabled_tag_ids(user_id))
    out: list[dict] = []
    for row in repo.list_role_filter_tags():
        tag_id = int(row["id"])
        item = {
            "id": tag_id,
            "keyword": row["keyword"],
            "kind": row["kind"],
        }
        if row["kind"] == "exclude":
            item["enabled"] = tag_id not in disabled
        out.append(item)
    return out


def set_tag_enabled(user_id: int, tag_id: int, enabled: bool) -> dict:
    tag = repo.get_role_filter_tag(tag_id)
    if tag is None:
        raise LookupError("Unknown role filter tag")
    if tag["kind"] != "exclude":
        raise ValueError("Only hide tags can be turned off")
    if enabled:
        repo.delete_user_tag_pref(user_id, tag_id)
    else:
        repo.upsert_disabled_tag_pref(user_id, tag_id)
    return {
        "id": int(tag["id"]),
        "keyword": tag["keyword"],
        "kind": tag["kind"],
        "enabled": enabled,
    }


def _clean_keyword(keyword: str, kind: str) -> tuple[str, str]:
    text = (keyword if isinstance(keyword, str) else "").strip()
    if text == "":
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
    saved["id"] = int(saved["id"])
    return saved


def edit_tag(tag_id: int, keyword: str, kind: str) -> dict:
    text, role_kind = _clean_keyword(keyword, kind)
    existing = repo.find_role_filter_tag(role_kind, text)
    if existing is not None and int(existing["id"]) != tag_id:
        raise ValueError("tag already exists")
    saved = repo.update_role_filter_tag(tag_id, text, role_kind)
    if saved is None:
        raise LookupError("Unknown role filter tag")
    saved["id"] = int(saved["id"])
    return saved


def mix_unhidden_roles(
    user_id: int | None,
    companies: list[dict],
    *,
    visa_only: bool = False,
) -> list[dict]:
    if not user_id or visa_only or not companies:
        return companies
    state = _unhide_exclude_state(user_id)
    if state is None:
        return companies
    disabled, active = state
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
            active=active,
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
    active: list[str],
    seen: set[str],
    tracking: dict,
) -> list[dict]:
    from relocation_jobs.panel.tracking import job_dict

    added: list[dict] = []
    country_key = (company.get("country") or "").strip().lower()
    company_name = (company.get("name") or "").strip()
    for row in extras:
        title = (row.get("title") or "").strip()
        if not title_unhidden(title, disabled, active):
            continue
        job = dict(row)
        job.pop("country", None)
        job.pop("company_name", None)
        job["title"] = title
        job["url"] = (job.get("url") or "").strip()
        job["description_text"] = ""
        job["visa_sponsorship"] = None
        job["closed_at"] = ""
        job["matches_default_filter"] = 0
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
