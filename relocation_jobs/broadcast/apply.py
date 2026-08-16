from __future__ import annotations

from relocation_jobs.broadcast.types import CapacityLimits, PositionAssignment


def _company_key(country: str, company_name: str) -> tuple[str, str]:
    return ((country or "").strip().lower(), (company_name or "").strip().lower())


def _job_key(job: dict) -> str:
    return (job.get("idempotency_key") or "").strip()


def apply_capacity_to_companies(
    companies: list[dict],
    *,
    limits: CapacityLimits,
    assignments: list[PositionAssignment] | tuple[PositionAssignment, ...],
    current_assignment_keys: set[tuple[str, str, str]] | None = None,
    bypass: bool = False,
) -> list[dict]:
    if bypass or limits.jobs_per_company is None:
        out = []
        for company in companies:
            row = dict(company)
            row["jobs_hidden_count"] = 0
            row["assigned_job_count"] = len(row.get("jobs") or [])
            row["upgrade_jobs"] = False
            out.append(row)
        return out

    by_company: dict[tuple[str, str], list[PositionAssignment]] = {}
    for assignment in assignments:
        key = _company_key(assignment.country, assignment.company_name)
        by_company.setdefault(key, []).append(assignment)
    out = []
    for company in companies:
        row = dict(company)
        key = _company_key(row.get("country") or "", row.get("name") or "")
        company_assignments = by_company.get(key, [])
        by_job = {assignment.job_key: assignment for assignment in company_assignments}
        jobs = list(row.get("jobs") or [])
        visible = []
        for job in jobs:
            assignment = by_job.get(_job_key(job))
            if not assignment:
                continue
            item = dict(job)
            item["broadcast_consumed"] = assignment.consumed_at is not None
            visible.append(item)
        existing_keys = {
            _job_key(job)
            for bucket in ("jobs", "rejected_jobs", "hidden_jobs", "not_for_me_jobs")
            for job in (row.get(bucket) or [])
        }
        for assignment in company_assignments:
            if assignment.job_key in existing_keys:
                continue
            if (
                current_assignment_keys is not None
                and (*key, assignment.job_key) in current_assignment_keys
            ):
                continue
            visible.append(
                {
                    "idempotency_key": assignment.job_key,
                    "url": assignment.job_url,
                    "title": assignment.job_title or "Previously shown role",
                    "country": assignment.country,
                    "company": assignment.company_name,
                    "listing_unavailable": True,
                    "broadcast_consumed": assignment.consumed_at is not None,
                }
            )
        hidden = max(0, len(jobs) - len([job for job in jobs if _job_key(job) in by_job]))
        row["jobs"] = visible
        row["jobs_hidden_count"] = hidden
        row["assigned_job_count"] = len(company_assignments)
        row["upgrade_jobs"] = hidden > 0
        out.append(row)
    return out
