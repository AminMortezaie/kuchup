from __future__ import annotations

import os
from html import escape
from urllib.parse import urlencode

import structlog
from flask import Response, redirect, render_template, send_from_directory

from relocation_jobs.catalog.repo import (
    get_public_job_by_slug,
    list_active_public_job_sitemap_entries,
)
from relocation_jobs.catalog.service import (
    SITE,
    company_workspace_path,
    iso_date,
    job_description_html,
    job_is_closed,
    job_is_public_listing,
    job_locality,
    job_posting_json_ld_text,
)
from relocation_jobs.core.auth import current_user_id, current_username
from relocation_jobs.core.location_tags import country_label
from relocation_jobs.core.paths import STATIC_DIR
from relocation_jobs.credits.service import credit_balance, spend_for_operation
from relocation_jobs.credits.types import CreditOperation
from relocation_jobs.positions.service import job_is_looking_to_apply, set_job_looking_to_apply
from relocation_jobs.users.entitlements import (
    consume_public_job_save,
    entitlement_status,
    free_public_job_saves_per_day,
    record_credited_public_job_save,
)

log = structlog.get_logger("relocation_jobs.web")

JOB_PAGE_CACHE = "public, max-age=300, stale-while-revalidate=86400"
HOMEPAGE_STATIC = STATIC_DIR / "homepage"


def _public_site_url() -> str:
    return (os.environ.get("PUBLIC_SITE_URL") or SITE).strip().rstrip("/")


def _not_found():
    path = HOMEPAGE_STATIC / "404.html"
    if path.is_file():
        resp = send_from_directory(HOMEPAGE_STATIC, "404.html")
        resp.headers["Cache-Control"] = "no-store"
        resp.status_code = 404
        return resp
    return Response(status=404)


def _page_job(slug: str) -> dict | None:
    job = get_public_job_by_slug(slug)
    if job is None or not job_is_public_listing(job):
        return None
    return job


def _already_tracking(job: dict, user_id: int) -> bool:
    return job_is_looking_to_apply(
        job.get("country") or "",
        job.get("company_name") or "",
        job.get("url") or "",
        user_id=user_id,
    )


def _primary_cta(job: dict, *, signed_in: bool) -> dict:
    slug = job.get("public_slug") or ""
    next_path = f"/jobs/{slug}/save"
    default = "Track & prepare this application in Kuchup"
    if not signed_in:
        return {
            "primary_href": f"/api/auth/google?{urlencode({'next': next_path})}",
            "primary_label": default,
        }
    uid = current_user_id()
    if uid and _already_tracking(job, uid):
        return {"primary_href": company_workspace_path(job), "primary_label": default}
    remaining = (entitlement_status(uid) if uid else {}).get("public_job_saves_remaining")
    if remaining is None:
        return {"primary_href": next_path, "primary_label": default}
    if remaining > 0:
        limit = free_public_job_saves_per_day()
        return {
            "primary_href": next_path,
            "primary_label": f"Track this application in Kuchup ({remaining} of {limit} free today)",
        }
    if uid and credit_balance(uid).total >= 1:
        return {"primary_href": next_path, "primary_label": "Use 1 credit to track this role"}
    return {
        "primary_href": "/pricing",
        "primary_label": "Buy credits or Full Access to track more roles today",
    }


def _job_page_context(job: dict, *, signed_in: bool, save_blocked: bool = False) -> dict:
    slug = job.get("public_slug") or ""
    company = (job.get("company_name") or "").strip() or "Employer"
    country = (job.get("country") or "").strip().lower()
    closed = job_is_closed(job)
    cta = {} if closed else _primary_cta(job, signed_in=signed_in)
    return {
        "job": job,
        "closed": closed,
        "title": (job.get("title") or "").strip() or "Role",
        "company": company,
        "location_label": job.get("location") or job_locality(job) or country_label(country),
        "country_label": country_label(country),
        "country_href": f"/relocation-jobs-{country}" if country else "/",
        "visa": job.get("visa_sponsorship") is True,
        "description_html": job_description_html(job),
        "json_ld": "" if closed else job_posting_json_ld_text(job),
        "canonical": f"{_public_site_url()}/jobs/{slug}",
        "primary_href": cta.get("primary_href", ""),
        "primary_label": cta.get("primary_label", ""),
        "employer_href": f"/jobs/{slug}/employer",
        "signed_in": signed_in,
        "nav_label": "Open workspace" if signed_in else "Sign in",
        "nav_title": (current_username() or "") if signed_in else "",
        "save_blocked": save_blocked,
    }


def _job_page_response(job: dict, *, save_blocked: bool = False) -> Response:
    signed_in = current_user_id() is not None
    closed = job_is_closed(job)
    html = render_template(
        "job_posting.html",
        **_job_page_context(job, signed_in=signed_in, save_blocked=save_blocked),
    )
    resp = Response(html, status=410 if closed else 200, mimetype="text/html")
    private = closed or signed_in or save_blocked
    resp.headers["Cache-Control"] = "no-store" if private else JOB_PAGE_CACHE
    return resp


def _mark_looking_to_apply(job: dict, user_id: int) -> None:
    set_job_looking_to_apply(
        job.get("country") or "",
        job.get("company_name") or "",
        job.get("url") or "",
        True,
        user_id=user_id,
    )


def _spend_public_save_credit(user_id: int, slug: str) -> bool:
    spent = spend_for_operation(
        user_id,
        CreditOperation.PUBLIC_JOB_SAVE,
        idempotency_key=f"public-job-save:{user_id}:{slug}",
        metadata={"slug": slug},
    )
    return bool(spent.get("spent"))


def _claim_public_save(job: dict, user_id: int, slug: str) -> Response | None:
    if _already_tracking(job, user_id):
        return None
    job_id = int(job.get("id") or 0)
    if not job_id:
        return _not_found()
    claimed = consume_public_job_save(user_id, job_id, slug)
    if not claimed.get("needs_credit"):
        return None
    if not _spend_public_save_credit(user_id, slug):
        resp = _job_page_response(job, save_blocked=True)
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp
    record_credited_public_job_save(user_id, job_id, slug)
    return None


def _xml_lastmod(row: dict) -> str:
    return iso_date(row.get("last_seen") or row.get("fetched") or "")


def register(app):
    @app.get("/jobs/<slug>")
    def public_job_page(slug: str):
        job = _page_job(slug)
        if job is None:
            return _not_found()
        return _job_page_response(job)

    @app.get("/jobs/<slug>/save")
    def public_job_save(slug: str):
        job = _page_job(slug)
        if job is None:
            return _not_found()
        if job_is_closed(job):
            return _job_page_response(job)
        uid = current_user_id()
        if not uid:
            resp = redirect(
                f"/api/auth/google?{urlencode({'next': f'/jobs/{slug}/save'})}"
            )
            resp.headers["X-Robots-Tag"] = "noindex"
            return resp
        blocked = _claim_public_save(job, uid, slug)
        if blocked is not None:
            return blocked
        try:
            _mark_looking_to_apply(job, uid)
        except LookupError:
            return _not_found()
        resp = redirect(company_workspace_path(job))
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.get("/jobs/<slug>/employer")
    def public_job_employer(slug: str):
        job = _page_job(slug)
        if job is None:
            return _not_found()
        dest = (job.get("url") or "").strip()
        if not dest:
            return _not_found()
        log.info(
            "employer_outbound",
            slug=slug,
            company=job.get("company_name") or "",
            url=dest,
        )
        resp = redirect(dest, code=302)
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.get("/sitemap-jobs.xml")
    def sitemap_jobs_xml():
        public_site_url = _public_site_url()
        entries: list[str] = []
        for row in list_active_public_job_sitemap_entries():
            slug = (row.get("public_slug") or "").strip()
            if not slug:
                continue
            loc = f"{public_site_url}/jobs/{escape(slug)}"
            lastmod = _xml_lastmod(row)
            entries.append(
                "\n".join((
                    "  <url>",
                    f"    <loc>{loc}</loc>",
                    f"    <lastmod>{lastmod}</lastmod>",
                    "  </url>",
                ))
            )
        body = "\n".join((
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *entries,
            "</urlset>",
            "",
        ))
        resp = Response(body, mimetype="application/xml")
        resp.headers["Cache-Control"] = JOB_PAGE_CACHE
        return resp
