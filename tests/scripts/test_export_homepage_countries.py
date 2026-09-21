from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXPORT_SCRIPT = ROOT / "scripts" / "export_homepage_countries.py"


def _export_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("REDIS_URL", None)
    env["PYTHONPATH"] = str(ROOT)
    return env


def test_export_runs_without_psycopg_pool(monkeypatch, tmp_path):
    out = tmp_path / "countries.json"
    env = _export_env(monkeypatch)
    replace_out = json.dumps(f"OUT = Path({json.dumps(str(out))})")
    runner = f"""
import sys
import types
from pathlib import Path

sys.path.insert(0, {str(ROOT)!r})
sys.modules["psycopg_pool"] = types.ModuleType("psycopg_pool")

root = Path({str(ROOT)!r})
code = (root / "scripts" / "export_homepage_countries.py").read_text(encoding="utf-8")
code = code.replace(
    'OUT = ROOT / "homepage" / "data" / "countries.json"',
    {replace_out},
)
ns = {{
    "__name__": "__main__",
    "__file__": str(root / "scripts" / "export_homepage_countries.py"),
    "Path": Path,
}}
exec(compile(code, "export_homepage_countries.py", "exec"), ns)
raise SystemExit(ns["main"]())
"""
    proc = subprocess.run(
        [sys.executable, "-c", runner],
        env=env,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    assert '"germany": "Germany"' in out.read_text(encoding="utf-8")


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


def test_custom_countries_import_without_psycopg_pool_module(monkeypatch):
    monkeypatch.delitem(sys.modules, "psycopg_pool", raising=False)
    sys.modules["psycopg_pool"] = types.ModuleType("psycopg_pool")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import importlib

    import relocation_jobs.catalog.custom_countries as cc

    importlib.reload(cc)
    assert cc.DEFAULT_COUNTRY_LABELS["uk"] == "United Kingdom"
