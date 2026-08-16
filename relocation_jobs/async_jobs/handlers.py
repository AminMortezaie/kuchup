from __future__ import annotations

from relocation_jobs.async_jobs.types import (
    ReconcileCountryOpportunities,
    ReconcileUserOpportunities,
)
from relocation_jobs.opportunities import service as opportunities_service


def handle_reconcile_user(message: ReconcileUserOpportunities) -> dict:
    return opportunities_service.refresh_user_opportunities(message.user_id)


def handle_reconcile_country(message: ReconcileCountryOpportunities) -> dict:
    return opportunities_service.refresh_users_for_country(message.country)
