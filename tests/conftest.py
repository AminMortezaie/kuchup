"""Shared fixtures: in-memory Postgres mock and catalog seed data."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from tests.helpers.postgres_mock import install_session_postgres_mock

FIXTURES = Path(__file__).parent / "fixtures"

_SESSION_ENV_KEYS = (
    "PANEL_ADMIN_USER",
    "PANEL_ADMIN_EMAILS",
    "PANEL_AUTH_DISABLED",
    "PANEL_SECRET_KEY",
    "PANEL_ALLOW_REGISTER",
    "PANEL_SCRAPE_ENABLED",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
)


def _seed_admin_user() -> dict:
    from relocation_jobs.users.repo import create_user, get_user_by_username

    admin = get_user_by_username("admin")
    if admin is not None:
        return admin
    return create_user(
        "admin",
        is_admin=True,
        email="admin@example.com",
        google_sub="test-sub-admin",
    )


@pytest.fixture(scope="session", autouse=True)
def _session_env():
    env_defaults = {
        "PANEL_ADMIN_USER": "admin",
        "PANEL_ADMIN_EMAILS": "admin@example.com",
        "PANEL_AUTH_DISABLED": "0",
        "PANEL_SECRET_KEY": "test-secret-key-fixed",
        "PANEL_ALLOW_REGISTER": "1",
        "PANEL_SCRAPE_ENABLED": "0",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    }
    saved = {key: os.environ.get(key) for key in _SESSION_ENV_KEYS}
    for key, value in env_defaults.items():
        os.environ[key] = value
    yield
    for key in _SESSION_ENV_KEYS:
        prior = saved[key]
        if prior is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prior


@pytest.fixture(scope="session")
def _session_postgres(_session_env):
    import relocation_jobs.core.db as core
    from relocation_jobs.db import init_db

    saved_url = os.environ.get("DATABASE_URL")
    original_connect = core._connect_postgres
    fake = install_session_postgres_mock()
    init_db()
    _seed_admin_user()

    yield fake

    fake.close()
    core._connect_postgres = original_connect
    core._pg["conn"] = None
    core.reset_db_initialized()
    if saved_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = saved_url


@pytest.fixture(autouse=True)
def _tests_use_postgres_countries(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from relocation_jobs.core.redis_client import reset_redis_client

    reset_redis_client()


@pytest.fixture(autouse=True)
def reset_custom_cities_cache():
    from relocation_jobs.catalog.cache import invalidate_country_cache
    from relocation_jobs.core.location_tags import (
        _invalidate_custom_cities_cache,
        _invalidate_custom_countries_cache,
        invalidate_country_labels_cache,
    )

    _invalidate_custom_cities_cache()
    _invalidate_custom_countries_cache()
    invalidate_country_labels_cache()
    invalidate_country_cache()
    try:
        from relocation_jobs.core.db import db_transaction, get_connection

        get_connection().execute("DELETE FROM custom_countries")
        with db_transaction() as conn:
            from relocation_jobs.catalog.custom_countries import seed_default_countries

            seed_default_countries(conn)
    except Exception:
        pass
    yield
    _invalidate_custom_cities_cache()
    _invalidate_custom_countries_cache()
    invalidate_country_cache()


@pytest.fixture(autouse=True)
def _app_schema(db):
    from relocation_jobs.core.db import get_connection
    from relocation_jobs.fetch import state as fetch_state
    from relocation_jobs.fetch.repo import clear_running_fetch_runs_for_tests

    get_connection().execute("DELETE FROM company_fetch_attempts")
    clear_running_fetch_runs_for_tests()
    fetch_state.reset_for_tests()
    yield


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("PANEL_DATA_DIR", str(data_dir))
    yield data_dir


@pytest.fixture
def db(tmp_data_dir, _session_postgres, request):
    import relocation_jobs.core.db as core

    if _session_postgres.closed:
        install_session_postgres_mock()
        core.reset_db_initialized()
        from relocation_jobs.db import init_db

        init_db()
        _seed_admin_user()
    elif request.node.get_closest_marker("fresh_db"):
        _session_postgres.clear_data()
    else:
        _session_postgres.clear_tracking()
    core._pg["conn"] = _session_postgres
    yield
    if request.node.get_closest_marker("fresh_db"):
        _session_postgres.clear_data()
        _seed_admin_user()
    else:
        _session_postgres.clear_tracking()


@pytest.fixture(scope="session")
def app(_session_postgres):
    from unittest.mock import patch

    import relocation_jobs.web.server as panel

    panel.bootstrap_app.cache_clear()
    with patch("relocation_jobs.web.server.init_db"):
        panel.bootstrap_app()
    panel.app.config["TESTING"] = True
    yield panel.app
    panel.bootstrap_app.cache_clear()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client, db):
    import relocation_jobs.core.db as core

    core._pg["conn"] = core.get_connection()
    admin = _seed_admin_user()
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = admin["id"]
        sess["username"] = admin["username"]
        sess.permanent = True
    yield client


@pytest.fixture
def v2_app(app):
    return app


@pytest.fixture
def v2_client(client):
    return client


@pytest.fixture
def v2_auth_client(auth_client):
    return auth_client


@pytest.fixture
def sample_country_data():
    return json.loads((FIXTURES / "country_uk_minimal.json").read_text())


@pytest.fixture
def seeded_catalog(db, sample_country_data):
    from relocation_jobs.catalog.repo import sync_country_catalog

    data = copy.deepcopy(sample_country_data)
    sync_country_catalog("uk", data)
    return data


@pytest.fixture
def seeded_catalog_v2(db):
    from tests.helpers.seed import seed_country

    return seed_country("uk", FIXTURES / "country_uk_minimal.json")


@pytest.fixture
def test_user(db):
    from relocation_jobs.users.repo import create_user

    return create_user(
        "testuser",
        email="testuser@example.com",
        google_sub="test-sub-testuser",
    )


@pytest.fixture
def mcp_documents(db):
    from relocation_jobs.mcp import repo as mcp_repo
    from relocation_jobs.mcp.types import ApplicationProfile
    from tests.mcp.conftest import GO_MASTER_TEX, JAVA_MASTER_TEX

    mcp_repo.save_master_resume(1, "go", GO_MASTER_TEX, label="Go backend")
    mcp_repo.save_master_resume(1, "java", JAVA_MASTER_TEX, label="Java backend")
    mcp_repo.save_profile(1, ApplicationProfile(full_name="Test User", email="test@example.com"))
    yield
