from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXPORT_SCRIPT = ROOT / "scripts" / "export_homepage_countries.py"


def _load_export_module():
    spec = importlib.util.spec_from_file_location("export_homepage_countries", EXPORT_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_export_runs_without_psycopg_pool(monkeypatch, tmp_path):
    out = tmp_path / "countries.json"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setitem(sys.modules, "psycopg_pool", types.ModuleType("psycopg_pool"))

    mod = _load_export_module()
    mod.OUT = out
    assert mod.main() == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["germany"] == "Germany"


def test_load_country_labels_store_skips_db_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from relocation_jobs.catalog.custom_countries import load_country_labels_store

    assert load_country_labels_store() == {}


def test_init_connection_pool_skips_without_database_url(monkeypatch):
    import relocation_jobs.core.db as core

    saved_pool = core._pool
    core._pool = None
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        core.init_connection_pool()
        assert core._pool is None
    finally:
        core._pool = saved_pool
