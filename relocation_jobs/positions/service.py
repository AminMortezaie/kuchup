from __future__ import annotations

from urllib.parse import urlparse

from relocation_jobs.core.job_identity import job_idempotency_key, normalize_job_url
from relocation_jobs.core.location_tags import (
    city_match_keys,
    company_expected_locations,
    job_fails_office_location_gate,
    job_matches_expected_locations,
    sync_company_location_fields,
)
from relocation_jobs.core.paths import supported_countries
from relocation_jobs.catalog.lookup import find_job_in_data
from relocation_jobs.catalog.repo import get_company, get_job_by_url, load_country_catalog
from relocation_jobs.positions import repo
from relocation_jobs.positions.types import JobStatusUpdate, TrackingFlags
from relocation_jobs.shared.coerce import as_bool
from relocation_jobs.users.repo import load_job_tracking


def _normalize_linkedin_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    host = (urlparse(raw).netloc or "").lower()
    if "linkedin.com" not in host:
        raise ValueError("Enter a LinkedIn profile URL (linkedin.com/in/…)")
    return raw


def _with_catalog_url(result: dict, catalog_url: str) -> dict:
    url = (catalog_url or "").strip() or (result.get("url") or "")
    if url:
        result["url"] = url
        result["idempotency_key"] = job_idempotency_key(url)
    return result


def _require_catalog_job(country_key: str, company_name: str, job_url: str) -> dict:
    job = get_job_by_url(job_url, company_name=company_name, country_key=country_key)
    if job is None:
        raise LookupError(f"Job not found: {company_name} — {job_url[:80]}")
    return job


def _validated(result: dict) -> dict:
    JobStatusUpdate(**result)
    return result


def _catalog_url(job: dict, job_url: str) -> str:
    return (job.get("url") or "").strip() or job_url


def _should_persist_wrong_location_hide(track: dict | None) -> bool:
    flags = TrackingFlags.from_row(track)
    if flags.not_for_me and flags.not_for_me_reason:
        return False
    if track and as_bool(track.get("location_gate_override")):
        return False
    return True


def _tracking_row_for_job(
    job_tracking: dict,
    *,
    country: str,
    company_name: str,
    job_url: str,
) -> dict | None:
    direct = job_tracking.get((country, company_name, normalize_job_url(job_url)))
    if direct is not None:
        return direct
    job_key = job_idempotency_key(job_url)
    if not job_key:
        return None
    for (t_country, t_company, t_url), track in job_tracking.items():
        if t_country != country or t_company != company_name:
            continue
        if job_idempotency_key(t_url) == job_key:
            return track
    return None


def _company_wrong_location_hits(company: dict, *, country: str) -> list[tuple[str, str, str]]:
    sync_company_location_fields(company, catalog_country=country)
    company_name = (company.get("name") or "").strip()
    if not company_name:
        return []
    hits: list[tuple[str, str, str]] = []
    for job in company.get("matching_jobs") or []:
        fails, _ = job_fails_office_location_gate(job, company, catalog_country=country)
        url = (job.get("url") or "").strip()
        if fails and url:
            hits.append((country, company_name, url))
    return hits


def _catalog_jobs_failing_location_gate(*, country_key: str | None) -> list[tuple[str, str, str]]:
    countries = [country_key] if country_key else sorted(supported_countries())
    hits: list[tuple[str, str, str]] = []
    for country in countries:
        data = load_country_catalog(country)
        if not data:
            continue
        for company in data.get("companies") or []:
            hits.extend(_company_wrong_location_hits(company, country=country))
    return hits


def _persist_wrong_location_hits(user_id: int, hits: list[tuple[str, str, str]]) -> int:
    if not hits:
        return 0
    countries = {country for country, _, _ in hits}
    country_filter = next(iter(countries)) if len(countries) == 1 else None
    job_tracking = load_job_tracking(user_id, country=country_filter)
    marked = 0
    for country, company_name, job_url in hits:
        track = _tracking_row_for_job(
            job_tracking,
            country=country,
            company_name=company_name,
            job_url=job_url,
        )
        if not _should_persist_wrong_location_hide(track):
            continue
        repo.set_not_for_me(
            user_id,
            country,
            company_name,
            job_url,
            not_for_me=True,
            reason="wrong_location",
        )
        marked += 1
    return marked


def set_job_applied(
    country_key: str,
    company_name: str,
    job_url: str,
    applied: bool,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_applied(
        user_id, country_key, company_name, storage_url, applied,
        job_title=job.get("title", ""),
    )
    repo.sync_company_applied(user_id, country_key, company_name)
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_rejected(
    country_key: str,
    company_name: str,
    job_url: str,
    rejected: bool,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_rejected(
        user_id, country_key, company_name, storage_url, rejected,
        job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_reapply(
    country_key: str,
    company_name: str,
    job_url: str,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.reapply(user_id, country_key, company_name, storage_url)
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_waiting_referral(
    country_key: str,
    company_name: str,
    job_url: str,
    waiting_referral: bool,
    *,
    user_id: int,
    linkedin_url: str = "",
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    normalized = _normalize_linkedin_url(linkedin_url) if waiting_referral else ""
    result = repo.set_waiting_referral(
        user_id, country_key, company_name, storage_url, waiting_referral,
        linkedin_url=normalized, job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_ats_score(
    country_key: str,
    company_name: str,
    job_url: str,
    ats_score: int | None,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_ats_score(
        user_id, country_key, company_name, storage_url, ats_score,
        job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_looking_to_apply(
    country_key: str,
    company_name: str,
    job_url: str,
    looking_to_apply: bool,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_looking_to_apply(
        user_id, country_key, company_name, storage_url, looking_to_apply,
        job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def job_is_looking_to_apply(
    country_key: str,
    company_name: str,
    job_url: str,
    *,
    user_id: int,
) -> bool:
    return repo.is_looking_to_apply(user_id, country_key, company_name, job_url)


def set_job_seen(
    country_key: str,
    company_name: str,
    job_url: str,
    seen: bool = True,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_seen(
        user_id, country_key, company_name, storage_url, seen,
        job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_pinned(
    country_key: str,
    company_name: str,
    job_url: str,
    pinned: bool = True,
    *,
    user_id: int,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_job_pinned(
        user_id, country_key, company_name, storage_url, pinned,
        job_title=job.get("title", ""),
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def set_job_not_for_me(
    country_key: str,
    company_name: str,
    job_url: str,
    *,
    user_id: int,
    not_for_me: bool = True,
    reason: str | None = None,
) -> dict:
    job = _require_catalog_job(country_key, company_name, job_url)
    storage_url = _catalog_url(job, job_url)
    result = repo.set_not_for_me(
        user_id, country_key, company_name, storage_url,
        not_for_me=not_for_me, reason=reason,
    )
    return _validated(_with_catalog_url(result, job.get("url", "")))


def apply_wrong_location_hides(
    user_id: int,
    *,
    country_key: str | None = None,
) -> int:
    return _persist_wrong_location_hits(
        user_id,
        _catalog_jobs_failing_location_gate(country_key=country_key),
    )


def reconcile_wrong_location_hides(
    user_id: int,
    *,
    country_key: str | None = None,
    city_label: str | None = None,
) -> int:
    rows = repo.load_wrong_location_hides(user_id, country_key)
    target_city_keys = city_match_keys(city_label) if city_label else set()
    restored = 0

    for row in rows:
        country = row["country"]
        company_name = row["company_name"]
        job_url = row["job_url"]

        company = get_company(country, company_name)
        if company is None:
            continue
        job = find_job_in_data({"companies": [company]}, company_name, job_url)
        if job is None:
            continue

        expected = company_expected_locations(company, catalog_country=country)
        if target_city_keys:
            office_keys = {key for loc in expected for key in city_match_keys(loc["city"])}
            if not (office_keys & target_city_keys):
                continue

        ok, _ = job_matches_expected_locations(job, expected)
        if not ok:
            continue

        repo.set_not_for_me(user_id, country, company_name, job_url, not_for_me=False)
        restored += 1

    return restored
