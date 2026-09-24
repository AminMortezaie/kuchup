from __future__ import annotations

import re

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


def _clean_keyword(keyword: str, kind: str) -> tuple[str, str]:
    text = (keyword if isinstance(keyword, str) else "").strip()
    if text == "":
        raise ValueError("keyword is required")
    role_kind = (kind or "").strip().lower()
    if role_kind not in ("include", "exclude"):
        raise ValueError("kind must be include or exclude")
    return text, role_kind


def _compact_keyword(keyword: str) -> str:
    return re.sub(r"[\s\-_/,]+", "", (keyword or "").lower())


def _expand_keyword_siblings(keywords: list[str], catalog: list[str]) -> list[str]:
    """Match fullstack ↔ full-stack ↔ full stack (same letters, different separators)."""
    wanted = {_compact_keyword(word) for word in keywords if word and _compact_keyword(word)}
    if not wanted:
        return list(keywords)
    out: list[str] = []
    seen: set[str] = set()
    for word in [*keywords, *catalog]:
        if not word or word in seen:
            continue
        if word in keywords or _compact_keyword(word) in wanted:
            out.append(word)
            seen.add(word)
    return out


def list_preferences(user_id: int) -> dict:
    disabled = set(repo.list_disabled_tag_ids(user_id))
    tags = []
    for row in repo.list_role_filter_tags():
        tag_id = int(row["id"])
        tags.append({
            "id": tag_id,
            "keyword": row["keyword"],
            "kind": row["kind"],
            "enabled": tag_id not in disabled,
            "personal": False,
        })
    mine = []
    for row in repo.list_user_role_tags(user_id):
        mine.append({
            "id": int(row["id"]),
            "keyword": row["keyword"],
            "kind": row["kind"],
            "enabled": True,
            "personal": True,
        })
    return {"tags": tags, "mine": mine}


def set_tag_enabled(user_id: int, tag_id: int, enabled: bool) -> dict:
    tag = repo.get_role_filter_tag(tag_id)
    if tag is None:
        raise LookupError("Unknown role filter tag")
    if enabled:
        repo.delete_user_tag_pref(user_id, tag_id)
    else:
        repo.upsert_disabled_tag_pref(user_id, tag_id)
    return {
        "id": int(tag["id"]),
        "keyword": tag["keyword"],
        "kind": tag["kind"],
        "enabled": enabled,
        "personal": False,
    }


def list_global_tags() -> list[dict]:
    return [
        {"id": int(row["id"]), "keyword": row["keyword"], "kind": row["kind"]}
        for row in repo.list_role_filter_tags()
    ]


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


def delete_tag(tag_id: int) -> None:
    if not repo.delete_role_filter_tag(tag_id):
        raise LookupError("Unknown role filter tag")


def add_user_tag(user_id: int, keyword: str, kind: str) -> dict:
    text, role_kind = _clean_keyword(keyword, kind)
    if repo.find_user_role_tag(user_id, role_kind, text) is not None:
        raise ValueError("tag already exists")
    saved = repo.insert_user_role_tag(user_id, text, role_kind)
    return {
        "id": int(saved["id"]),
        "keyword": saved["keyword"],
        "kind": saved["kind"],
        "enabled": True,
        "personal": True,
    }


def delete_user_tag(user_id: int, tag_id: int) -> None:
    if not repo.delete_user_role_tag(user_id, tag_id):
        raise LookupError("Unknown personal tag")


def _title_hits(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    folded = (title or "").lower()
    return any(keyword in folded for keyword in keywords)


def _passes_board_filters(
    title: str,
    *,
    enabled_includes: list[str],
    disabled_includes: list[str],
    personal_excludes: list[str],
) -> bool:
    if _title_hits(title, personal_excludes):
        return False
    if not disabled_includes:
        return True
    if not _title_hits(title, disabled_includes):
        return True
    return _title_hits(title, enabled_includes)


def title_unhidden(
    title: str,
    *,
    disabled_excludes: list[str],
    active_excludes: list[str],
    personal_includes: list[str],
) -> bool:
    from relocation_jobs.scrape.relevance import hidden_by_active_excludes

    # Personal include overrides global excludes (personal excludes filtered elsewhere).
    if _title_hits(title, personal_includes):
        return True
    if not disabled_excludes:
        return False
    if not _title_hits(title, disabled_excludes):
        return False
    return not hidden_by_active_excludes(title, active_excludes)


def _user_board_state(user_id: int) -> dict:
    disabled_ids = set(repo.list_disabled_tag_ids(user_id))
    tags = repo.list_role_filter_tags()
    catalog = [row["keyword"] for row in tags]
    enabled_includes = [
        row["keyword"] for row in tags
        if row["kind"] == "include" and int(row["id"]) not in disabled_ids
    ]
    disabled_includes = _expand_keyword_siblings(
        [
            row["keyword"] for row in tags
            if row["kind"] == "include" and int(row["id"]) in disabled_ids
        ],
        catalog,
    )
    disabled_excludes = [
        row["keyword"] for row in tags
        if row["kind"] == "exclude" and int(row["id"]) in disabled_ids
    ]
    active_excludes = [
        row["keyword"] for row in tags
        if row["kind"] == "exclude" and int(row["id"]) not in disabled_ids
    ]
    mine = repo.list_user_role_tags(user_id)
    personal_includes = _expand_keyword_siblings(
        [row["keyword"] for row in mine if row["kind"] == "include"],
        catalog,
    )
    personal_excludes = _expand_keyword_siblings(
        [row["keyword"] for row in mine if row["kind"] == "exclude"],
        catalog,
    )
    return {
        "enabled_includes": enabled_includes,
        "disabled_includes": disabled_includes,
        "disabled_excludes": disabled_excludes,
        "active_excludes": active_excludes + personal_excludes,
        "personal_includes": personal_includes,
        "personal_excludes": personal_excludes,
    }


def mix_unhidden_roles(
    user_id: int | None,
    companies: list[dict],
    *,
    visa_only: bool = False,
) -> list[dict]:
    if not user_id or visa_only or not companies:
        return companies
    state = _user_board_state(user_id)
    needs_mix = bool(state["disabled_excludes"] or state["personal_includes"])
    needs_filter = bool(state["disabled_includes"] or state["personal_excludes"])
    if not needs_mix and not needs_filter:
        return companies

    if needs_filter:
        for company in companies:
            jobs = [
                job for job in (company.get("jobs") or [])
                if _passes_board_filters(
                    (job.get("title") or "").strip(),
                    enabled_includes=state["enabled_includes"],
                    disabled_includes=state["disabled_includes"],
                    personal_excludes=state["personal_excludes"],
                )
            ]
            company["jobs"] = jobs
            company["job_count"] = len(jobs)

    if not needs_mix:
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
            state=state,
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
    state: dict,
    seen: set[str],
    tracking: dict,
) -> list[dict]:
    from relocation_jobs.panel.tracking import job_dict

    added: list[dict] = []
    country_key = (company.get("country") or "").strip().lower()
    company_name = (company.get("name") or "").strip()
    for row in extras:
        title = (row.get("title") or "").strip()
        if not title_unhidden(
            title,
            disabled_excludes=state["disabled_excludes"],
            active_excludes=state["active_excludes"],
            personal_includes=state["personal_includes"],
        ):
            continue
        if not _passes_board_filters(
            title,
            enabled_includes=state["enabled_includes"],
            disabled_includes=state["disabled_includes"],
            personal_excludes=state["personal_excludes"],
        ):
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
