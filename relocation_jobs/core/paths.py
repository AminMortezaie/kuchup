"""Project paths and country configuration."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE_DIR = PROJECT_ROOT / "relocation_jobs"
STATIC_DIR = PACKAGE_DIR / "static"


def supported_countries() -> frozenset[str]:
    from relocation_jobs.core.location_tags import supported_country_keys

    return supported_country_keys()


def country_archive_filename(country_key: str) -> str:
    key = (country_key or "").strip().lower()
    if not key:
        return ""
    return f"{key}_companies.json"


def data_dir() -> Path:
    raw = os.environ.get("PANEL_DATA_DIR", "").strip()
    if raw:
        return Path(raw)
    return PROJECT_ROOT / "data"


def ensure_data_dir() -> Path:
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
