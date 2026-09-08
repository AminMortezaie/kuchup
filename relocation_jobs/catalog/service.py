from __future__ import annotations

import json
import os
from datetime import date, timedelta
from email.utils import formatdate
from xml.sax.saxutils import escape as xml_escape

from bs4 import BeautifulSoup

from relocation_jobs.core.location_tags import country_label
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
LINKEDIN_DESCRIPTION_TAGS = frozenset(
    {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u"}
)


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
    loc = (job.get("location") or "").strip() or (job.get("city") or "").strip()
    if not loc:
        return ""
    loc = loc.split("(")[0].strip()
    return loc.split(",")[0].strip()


def job_location_label(job: dict) -> str:
    city = job_locality(job)
    region = country_label(job.get("country") or "") or ""
    if city and region:
        if region.lower() in city.lower():
            return city
        return f"{city}, {region}"
    return city or region


def job_is_closed(job: dict) -> bool:
    return bool((job.get("closed_at") or "").strip())


def skip_closed_unengaged(
    job: dict,
    *,
    applied: bool = False,
    looking_to_apply: bool = False,
) -> bool:
    if not job_is_closed(job):
        return False
    return not applied and not looking_to_apply


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


def job_posting_description(job: dict) -> str:
    html = job_description_html(job)
    return f"{html}{KUCHUP_NOTE}" if html else KUCHUP_NOTE


def job_apply_url(job: dict, site: str = SITE) -> str:
    slug = (job.get("public_slug") or "").strip()
    return f"{site.rstrip('/')}/jobs/{slug}"


def job_posting_json_ld(job: dict) -> dict:
    company = (job.get("company_name") or "").strip() or "Employer"
    title = (job.get("title") or "").strip() or "Role"
    slug = (job.get("public_slug") or "").strip()
    page_url = job_apply_url(job)
    posted = iso_date(job.get("fetched") or job.get("last_seen") or "")
    country = iso_country_code(job.get("country") or "")
    return {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": f"{title} at {company} (Visa Sponsorship)",
        "description": job_posting_description(job),
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


def group_public_jobs_by_country(jobs: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for job in jobs:
        key = (job.get("country") or "").strip().lower()
        groups.setdefault(key, []).append(job)
    ordered = sorted(groups.items(), key=lambda item: (country_label(item[0]) or item[0]).lower())
    return [
        {
            "key": key,
            "label": country_label(key) or key,
            "href": f"/jobs?country={key}" if key else "/jobs",
            "jobs": items,
        }
        for key, items in ordered
    ]


def public_jobs_item_list_json_ld(jobs: list[dict], page_url: str) -> str:
    elements = [
        {
            "@type": "ListItem",
            "position": index,
            "url": job_apply_url(job),
            "name": (job.get("title") or "").strip() or "Role",
        }
        for index, job in enumerate(jobs, start=1)
        if (job.get("public_slug") or "").strip()
    ]
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "url": page_url,
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _cdata(text: str) -> str:
    safe = (text or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _linkedin_description_html(job: dict) -> str:
    soup = BeautifulSoup(job_posting_description(job), "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in LINKEDIN_DESCRIPTION_TAGS:
            tag.unwrap()
            continue
        tag.attrs = {}
    body = soup.body or soup
    return "".join(str(child) for child in body.children).strip()


def _linkedin_job_xml(job: dict, site: str, company_id: str, poster_email: str) -> str:
    partner_id = str(job.get("id") or "")[:40]
    title = (job.get("title") or "").strip() or "Role"
    apply_url = job_apply_url(job, site)
    fields = [
        ("partnerJobId", partner_id),
        ("company", "Kuchup"),
        ("title", title),
        ("description", _linkedin_description_html(job)),
        ("applyUrl", apply_url),
        ("companyId", company_id),
        ("location", job_location_label(job)),
        ("posterEmail", poster_email),
    ]
    lines = ["    <job>"]
    for name, value in fields:
        lines.append(f"      <{name}>{_cdata(value)}</{name}>")
    lines.append("    </job>")
    return "\n".join(lines)


def linkedin_jobs_xml_text(jobs: list[dict], *, site: str = SITE) -> str:
    company_id = (os.environ.get("LINKEDIN_COMPANY_ID") or "").strip()
    poster_email = (os.environ.get("LINKEDIN_JOB_POSTER_EMAIL") or "").strip()
    job_blocks = [
        _linkedin_job_xml(job, site, company_id, poster_email)
        for job in jobs
        if (job.get("public_slug") or "").strip()
    ]
    body = "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<source>",
        f"    <lastBuildDate>{formatdate(usegmt=True)}</lastBuildDate>",
        f"    <publisherUrl>{xml_escape(site)}</publisherUrl>",
        "    <publisher>Kuchup</publisher>",
        f"    <expectedJobCount>{len(job_blocks)}</expectedJobCount>",
        *job_blocks,
        "</source>",
        "",
    ))
    return body
