from __future__ import annotations

import pytest

from relocation_jobs.async_jobs.enqueue import enqueue_user_opportunity_refresh
from relocation_jobs.opportunities.service import ensure_user_preferences_row
from relocation_jobs.users.repo import create_user
from tests.helpers.seed import seed_free_assignments


def test_ensure_user_preferences_row_is_idempotent(db):
    user = create_user("oppuser", email="oppuser@example.com", google_sub="sub-opp")
    uid = int(user["id"])
    ensure_user_preferences_row(uid)
    ensure_user_preferences_row(uid)
    from relocation_jobs.opportunities import repo as opportunities_repo

    assert opportunities_repo.needs_opportunity_bootstrap(uid) is True


def test_production_repos_do_not_create_assignment_rows():
    from relocation_jobs.broadcast import repo as broadcast_repo
    from relocation_jobs.opportunities import repo as opportunities_repo

    assert not hasattr(broadcast_repo, "ensure_company_assignments")
    assert not hasattr(opportunities_repo, "replace_user_opportunities")


def test_enqueue_without_writer_raises(db, seeded_catalog_v2, monkeypatch):
    monkeypatch.delenv("SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL", raising=False)
    monkeypatch.delenv("ROLE_PROPAGATOR_BIN", raising=False)
    user = create_user("syncuser", email="syncuser@example.com", google_sub="sub-sync")
    with pytest.raises(RuntimeError, match="assignment writer missing"):
        enqueue_user_opportunity_refresh(int(user["id"]))


def test_seed_free_assignments_fills_board_rows(db, seeded_catalog_v2):
    user = create_user("seeduser", email="seeduser@example.com", google_sub="sub-seed")
    count = seed_free_assignments(int(user["id"]), ["uk"])
    assert count >= 1
