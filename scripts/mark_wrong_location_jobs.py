#!/usr/bin/env python3
"""One-shot: persist wrong-location catalog jobs as not_for_me in job_tracking."""

from __future__ import annotations

import argparse
import sys

from relocation_jobs.catalog.repo import load_country_catalog
from relocation_jobs.core.location_tags import job_fails_office_location_gate, sync_company_location_fields
from relocation_jobs.core.paths import supported_countries
from relocation_jobs.panel.tracking import resolve_track
from relocation_jobs.positions.service import (
    _should_persist_wrong_location_hide,
    apply_wrong_location_hides,
)
from relocation_jobs.users.repo import list_user_ids, load_job_tracking


def _catalog_url(job: dict) -> str:
    return (job.get("url") or "").strip()


def find_wrong_location_jobs(*, country_key: str | None = None) -> list[dict]:
    countries = [country_key] if country_key else sorted(supported_countries())
    hits: list[dict] = []
    for country in countries:
        data = load_country_catalog(country)
        if not data:
            continue
        for company in data.get("companies") or []:
            sync_company_location_fields(company, catalog_country=country)
            company_name = (company.get("name") or "").strip()
            if not company_name:
                continue
            for job in company.get("matching_jobs") or []:
                fails, reason = job_fails_office_location_gate(
                    job, company, catalog_country=country,
                )
                if not fails:
                    continue
                url = _catalog_url(job)
                if not url:
                    continue
                hits.append({
                    "country": country,
                    "company_name": company_name,
                    "job_url": url,
                    "title": (job.get("title") or "").strip(),
                    "reason": reason or "location mismatch",
                })
    return hits


def count_for_user(user_id: int, hits: list[dict]) -> int:
    job_tracking = load_job_tracking(user_id)
    marked = 0
    for hit in hits:
        track = resolve_track(
            job_tracking,
            country=hit["country"],
            company_name=hit["company_name"],
            job={"url": hit["job_url"]},
        )
        if _should_persist_wrong_location_hide(track or None):
            marked += 1
    return marked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", help="Limit to one country key (e.g. germany)")
    parser.add_argument("--user-id", type=int, help="Limit to one user id (default: all users)")
    parser.add_argument("--dry-run", action="store_true", help="List matches without writing")
    args = parser.parse_args(argv)

    if args.country and args.country not in supported_countries():
        print(f"Unknown country: {args.country}", file=sys.stderr)
        return 1

    hits = find_wrong_location_jobs(country_key=args.country)
    print(f"Catalog wrong-location jobs: {len(hits)}")
    for hit in hits[:20]:
        print(f"  [{hit['country']}] {hit['company_name']} — {hit['title'][:60]}")
    if len(hits) > 20:
        print(f"  … and {len(hits) - 20} more")

    user_ids = [args.user_id] if args.user_id else list_user_ids()
    if not user_ids:
        print("No users in database.", file=sys.stderr)
        return 1

    total_marked = 0
    for user_id in user_ids:
        if args.dry_run:
            n = count_for_user(user_id, hits)
        else:
            n = apply_wrong_location_hides(user_id, country_key=args.country)
        total_marked += n
        verb = "would mark" if args.dry_run else "marked"
        print(f"User {user_id}: {verb} {n} position(s)")

    print(f"Done — {total_marked} tracking row(s) {'would be ' if args.dry_run else ''}updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
