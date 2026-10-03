from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOMEPAGE = ROOT / "homepage" / "components"


def _read(name: str) -> str:
    return (HOMEPAGE / name).read_text(encoding="utf-8")


def test_homepage_header_and_hero_link_jobs_and_engineering():
    header = _read("Header.tsx")
    hero = _read("HeroSearch.tsx")
    for path in ("/jobs", "/engineering"):
        assert f'href: "{path}"' in header
        assert f'href="{path}"' in hero


def test_footer_links_jobs_and_engineering():
    footer = _read("Footer.tsx")
    assert 'href: "/jobs"' in footer
    assert 'href: "/engineering"' in footer
