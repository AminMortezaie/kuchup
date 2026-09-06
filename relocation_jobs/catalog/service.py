from __future__ import annotations

import json
from datetime import date, timedelta

from relocation_jobs.core.slug import slug_from_name
from relocation_jobs.scrape.descriptions import format_job_description

COUNTRY_ISO = {
    "germany": "DE",
    "ireland": "IE",
    "netherlands": "NL",
    "portugal": "PT",
    "uk": "GB",
}

KUCHUP_NOTE = (
    "<br><br> <strong>Note:</strong> This role is curated by Kuchup. "
    "Apply via our workspace to track your application and tailor your CV."
)

SITE = "https://kuchup.com"
LOGO_URL = f"{SITE}/logo.png"
VALID_THROUGH_DAYS = 30


def iso_country_code(country_key: str) -> str:
    key = (country_key or "").strip().lower()
    if key in COUNTRY_ISO:
        return COUNTRY_ISO[key]
    return key[:2].upper() if key else ""


def iso_date(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return date.today().isoformat()


def valid_through_date(date_posted: str, closed_at: str = "") -> str:
    if (closed_at or "").strip():
        return iso_date(closed_at)
    posted = date.fromisoformat(iso_date(date_posted))
    return (posted + timedelta(days=VALID_THROUGH_DAYS)).isoformat()


def job_locality(job: dict) -> str:
    loc = (job.get("location") or "").strip()
    if loc:
        return loc.split(",")[0].strip()
    return (job.get("city") or "").strip()


def job_is_closed(job: dict) -> bool:
    return bool((job.get("closed_at") or "").strip())


def job_is_public_listing(job: dict) -> bool:
    if job.get("visa_sponsorship") is True:
        return True
    return job_is_closed(job) and bool((job.get("public_slug") or "").strip())


def company_workspace_path(job: dict) -> str:
    country = (job.get("country") or "").strip().lower()
    slug = slug_from_name(job.get("company_name") or "")
    if not country or not slug:
        return "/panel"
    return f"/company/{country}/{slug}"


def job_description_html(job: dict) -> str:
    _readable, display_html = format_job_description(job.get("description_text") or "")
    return display_html


def job_posting_json_ld(job: dict) -> dict:
    company = (job.get("company_name") or "").strip() or "Employer"
    title = (job.get("title") or "").strip() or "Role"
    slug = (job.get("public_slug") or "").strip()
    page_url = f"{SITE}/jobs/{slug}"
    posted = iso_date(job.get("fetched") or job.get("last_seen") or "")
    country = iso_country_code(job.get("country") or "")
    html = job_description_html(job)
    return {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": f"{title} at {company} (Visa Sponsorship)",
        "description": f"{html}{KUCHUP_NOTE}" if html else KUCHUP_NOTE,
        "identifier": {
            "@type": "PropertyValue",
            "name": "Kuchup",
            "value": str(job.get("id") or slug),
        },
        "datePosted": posted,
        "validThrough": valid_through_date(posted, job.get("closed_at") or ""),
        "employmentType": "FULL_TIME",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "Kuchup",
            "sameAs": SITE,
            "logo": LOGO_URL,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job_locality(job),
                "addressCountry": country,
            },
        },
        "url": page_url,
        "applyUrl": page_url,
    }


def job_posting_json_ld_text(job: dict) -> str:
    return json.dumps(job_posting_json_ld(job), ensure_ascii=False, separators=(",", ":"))
