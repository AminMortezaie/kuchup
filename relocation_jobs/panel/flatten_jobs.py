from __future__ import annotations

from relocation_jobs.catalog.service import skip_closed_unengaged
from relocation_jobs.panel.flatten_orphans import stats_job_entry
from relocation_jobs.panel.tracking import catalog_not_for_me, job_dict, resolve_track, resolve_track_flags
from relocation_jobs.positions.state import (
    derive_bucket,
    passes_position_filters,
    position_view_from_row,
)
from relocation_jobs.positions.types import PositionBucket, PositionFilters, TrackingFlags
from relocation_jobs.shared.coerce import as_bool


def not_for_me_entry(
    job: dict,
    *,
    company_name: str,
    company: dict,
    country_key: str,
    country_label: str,
    job_tracking: dict | None,
    status_history: dict | None,
    mcp_applications: dict | None,
) -> dict:
    return job_dict(
        job,
        company_name=company_name,
        company=company,
        country_key=country_key,
        country_label=country_label,
        job_tracking=job_tracking,
        status_history=status_history,
        mcp_applications=mcp_applications,
    )


def partition_stored_jobs(
    stored_jobs: list[dict],
    *,
    user_id: int | None,
    job_tracking: dict,
    company_name: str,
    company: dict,
    country_key: str,
    country_label: str,
    status_history: dict,
    mcp_applications: dict | None,
    visa_only: bool,
    position_filters: PositionFilters,
) -> tuple[list[dict], list[dict], list[dict], int, int]:
    jobs: list[dict] = []
    not_for_me_jobs: list[dict] = []
    rejected_jobs: list[dict] = []
    positions_not_for_me = 0
    positions_hidden_by_visa = 0

    for job in stored_jobs:
        if user_id:
            track = resolve_track(
                job_tracking, country=country_key, company_name=company_name, job=job,
            )
            view = position_view_from_row(track)
            if view.bucket == PositionBucket.NOT_FOR_ME:
                positions_not_for_me += 1
                not_for_me_jobs.append(not_for_me_entry(
                    job,
                    company_name=company_name,
                    company=company,
                    country_key=country_key,
                    country_label=country_label,
                    job_tracking=job_tracking,
                    status_history=status_history,
                    mcp_applications=mcp_applications,
                ))
                continue
            if skip_closed_unengaged(
                job,
                applied=bool(track.get("applied")),
                looking_to_apply=bool(track.get("looking_to_apply")),
            ):
                continue
        elif catalog_not_for_me(job):
            positions_not_for_me += 1
            not_for_me_jobs.append(not_for_me_entry(
                job,
                company_name=company_name,
                company=company,
                country_key=country_key,
                country_label=country_label,
                job_tracking=None,
                status_history=None,
                mcp_applications=mcp_applications,
            ))
            continue

        elif skip_closed_unengaged(
            job,
            applied=bool(job.get("applied")),
            looking_to_apply=False,
        ):
            continue

        if visa_only and job.get("visa_sponsorship") is not True:
            positions_hidden_by_visa += 1
            continue

        job_entry = job_dict(
            job,
            company_name=company_name,
            company=company,
            country_key=country_key,
            country_label=country_label,
            job_tracking=job_tracking if user_id else None,
            status_history=status_history if user_id else None,
            mcp_applications=mcp_applications if user_id else None,
        )
        flags = TrackingFlags.from_job_panel_dict(job_entry)
        if derive_bucket(flags) == PositionBucket.REJECTED:
            rejected_jobs.append(job_entry)
            continue
        if not passes_position_filters(flags, position_filters):
            continue
        jobs.append(job_entry)

    return jobs, not_for_me_jobs, rejected_jobs, positions_not_for_me, positions_hidden_by_visa


def partition_stored_jobs_for_stats(
    stored_jobs: list[dict],
    *,
    user_id: int | None,
    job_tracking: dict,
    alias_index: dict[tuple[str, str, str], dict],
    company_name: str,
    company: dict,
    country_key: str,
    visa_only: bool,
    position_filters: PositionFilters,
) -> tuple[list[dict], list[dict], int]:
    jobs: list[dict] = []
    rejected_jobs: list[dict] = []
    positions_not_for_me = 0

    for job in stored_jobs:
        track: dict = {}
        if user_id:
            track = resolve_track_flags(
                job_tracking,
                alias_index,
                country=country_key,
                company_name=company_name,
                job=job,
            )
            view = position_view_from_row(track)
            if view.bucket == PositionBucket.NOT_FOR_ME:
                positions_not_for_me += 1
                continue
            if skip_closed_unengaged(
                job,
                applied=bool(track.get("applied")),
                looking_to_apply=bool(track.get("looking_to_apply")),
            ):
                continue
        elif catalog_not_for_me(job):
            positions_not_for_me += 1
            continue
        elif skip_closed_unengaged(
            job,
            applied=bool(job.get("applied")),
            looking_to_apply=False,
        ):
            continue

        if visa_only and job.get("visa_sponsorship") is not True:
            continue

        applied = bool(track.get("applied")) if user_id else bool(job.get("applied"))
        rejected = as_bool(track.get("rejected")) if user_id else as_bool(job.get("rejected"))
        flags = TrackingFlags(
            applied=applied,
            rejected=rejected,
            not_for_me=bool(track.get("not_for_me")) if user_id else bool(job.get("not_for_me")),
            looking_to_apply=bool(track.get("looking_to_apply")) if user_id else False,
        )
        if derive_bucket(flags) == PositionBucket.REJECTED:
            rejected_jobs.append(stats_job_entry(
                applied=applied,
                visa_sponsorship=job.get("visa_sponsorship"),
            ))
            continue
        if not passes_position_filters(flags, position_filters):
            continue
        jobs.append(stats_job_entry(
            applied=applied,
            visa_sponsorship=job.get("visa_sponsorship"),
            fetched=job.get("fetched", ""),
            last_seen=job.get("last_seen", ""),
        ))

    return jobs, rejected_jobs, positions_not_for_me
