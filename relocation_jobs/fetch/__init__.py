from relocation_jobs.fetch.service import fetch_company
from relocation_jobs.fetch.types import AttemptStatus, CompanyFetchAttempt

__all__ = [
    "AttemptStatus",
    "CompanyFetchAttempt",
    "bootstrap_scheduler",
    "fetch_company",
    "run_fetch_cycle",
    "run_scheduled_pass",
    "start_company_fetch",
    "start_country_fetch",
]


def __getattr__(name: str):
    if name in ("bootstrap_scheduler", "run_fetch_cycle", "run_scheduled_pass"):
        from relocation_jobs.fetch import scheduler
        return getattr(scheduler, name)
    if name in ("start_country_fetch", "start_company_fetch"):
        from relocation_jobs.fetch import runner
        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
