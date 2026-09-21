from __future__ import annotations

from relocation_jobs.broadcast.types import CapacityLimits
from relocation_jobs.opportunities.types import CompanyCandidate, OpportunityRow


def company_key(country: str, company_name: str) -> tuple[str, str]:
    return ((country or "").strip().lower(), (company_name or "").strip().lower())


def reconcile_sticky_slots(
    *,
    existing: list[OpportunityRow],
    ranked_open: list[CompanyCandidate],
    limits: CapacityLimits,
    is_admin: bool,
) -> list[OpportunityRow]:
    by_open = {
        company_key(c.country, c.company_name): c
        for c in ranked_open
        if c.open_job_count > 0
    }
    kept: list[OpportunityRow] = []
    kept_keys: set[tuple[str, str]] = set()
    for row in existing:
        key = company_key(row.country, row.company_name)
        if not row.engaged and key not in by_open:
            continue
        kept.append(row)
        kept_keys.add(key)

    cap = None if is_admin else limits.company_slots
    if cap is not None and len(kept) > cap:
        kept.sort(
            key=lambda r: (r.engaged, r.newest_fetched or "", r.company_name.lower()),
            reverse=True,
        )
        kept = kept[:cap]
        kept_keys = {company_key(r.country, r.company_name) for r in kept}

    ranked = sorted(
        by_open.values(),
        key=lambda c: (c.newest_fetched or "", c.company_name.lower()),
        reverse=True,
    )
    for candidate in ranked:
        if cap is not None and len(kept) >= cap:
            break
        key = company_key(candidate.country, candidate.company_name)
        if key in kept_keys:
            continue
        kept.append(
            OpportunityRow(
                country=candidate.country,
                company_name=candidate.company_name,
                newest_fetched=candidate.newest_fetched or "",
                revealed_job_count=0,
                engaged=False,
            )
        )
        kept_keys.add(key)

    out: list[OpportunityRow] = []
    for row in kept:
        key = company_key(row.country, row.company_name)
        candidate = by_open.get(key)
        newest = candidate.newest_fetched if candidate else row.newest_fetched
        out.append(
            OpportunityRow(
                country=row.country,
                company_name=row.company_name,
                newest_fetched=newest or "",
                revealed_job_count=0,
                engaged=row.engaged,
            )
        )
    return out
