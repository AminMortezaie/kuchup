from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from relocation_jobs.catalog.repo import get_company, sync_company_board_to_catalog


def test_panel_page_keeps_private_app_shell(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/panel")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="loginPanel"' in body
    assert 'src="/static/js/main.js' in body


def test_legacy_preview_path_redirects_to_root(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/preview", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/")


def test_legacy_app_path_redirects_to_panel(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/app", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/panel")


def test_public_overview_returns_catalog_snapshot(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/api/public/overview")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["has_data"] is True
    assert payload["totals"]["companies"] >= 1
    assert payload["totals"]["jobs"] >= 2
    assert payload["countries"]
    uk = next(row for row in payload["countries"] if row["country"] == "uk")
    assert uk["companies"] >= 1
    assert uk["jobs"] >= 2
    assert "country_meta" in payload


def test_public_preview_returns_company_sample_without_user_state(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/api/public/preview")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["companies"]
    company = payload["companies"][0]
    assert "name" in company
    assert "job_count" in company
    assert "preview_jobs" not in company
    assert "positions_applied" not in company
    assert "title" not in str(payload["companies"])


def test_public_preview_accepts_country_and_query_filters(v2_client, seeded_catalog_v2):
    del seeded_catalog_v2
    resp = v2_client.get("/api/public/preview?country=uk&limit=12")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["country"] == "uk"
    assert all(row["country"] == "uk" for row in payload["companies"])


def test_public_preview_returns_only_positive_sponsorship_positions(
    v2_client,
    seeded_catalog_v2,
):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"][0]["visa_sponsorship"] = True
    company["matching_jobs"][1]["visa_sponsorship"] = False
    sync_company_board_to_catalog("uk", company)

    resp = v2_client.get("/api/public/preview?country=uk&q=backend")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["sponsorship_filter"] == "positive_only"
    assert payload["meta"]["positions_returned"] == 1
    assert payload["featured_companies"]
    assert payload["positions"] == [
        {
            "company_name": "Acme Backend Ltd",
            "country": "uk",
            "country_label": "United Kingdom",
            "last_seen": "2025-06-01",
            "location": "London (United Kingdom)",
            "sponsorship_signal": "positive",
            "title": "Senior Backend Engineer",
            "url": "https://boards.greenhouse.io/acmebackend/jobs/123456?gh_jid=123456",
        }
    ]


def test_public_preview_omits_closed_visa_positions(
    v2_client,
    seeded_catalog_v2,
):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"][0]["visa_sponsorship"] = True
    company["matching_jobs"][0]["closed_at"] = "2026-09-07T00:00:00+00:00"
    company["matching_jobs"][1]["visa_sponsorship"] = False
    sync_company_board_to_catalog("uk", company)

    resp = v2_client.get("/api/public/preview?country=uk&q=backend")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["positions_returned"] == 0
    assert payload["positions"] == []


def test_public_preview_always_returns_featured_companies(
    v2_client,
    seeded_catalog_v2,
):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"][0]["visa_sponsorship"] = True
    sync_company_board_to_catalog("uk", company)

    payload = v2_client.get("/api/public/preview?country=uk&q=backend").get_json()

    assert payload["featured_companies"] == [
        {
            "careers_url": "https://boards.greenhouse.io/acmebackend",
            "city": "London (United Kingdom)",
            "country": "uk",
            "country_label": "United Kingdom",
            "name": "Acme Backend Ltd",
            "visa_role_count": 1,
        }
    ]
    assert payload["meta"]["featured_scope"] == "country"


def test_public_preview_suggests_sponsoring_companies_elsewhere(
    v2_client,
    seeded_catalog_v2,
):
    del seeded_catalog_v2
    company = get_company("uk", "Acme Backend Ltd")
    assert company is not None
    company["matching_jobs"][0]["visa_sponsorship"] = True
    sync_company_board_to_catalog("uk", company)

    payload = v2_client.get(
        "/api/public/preview?country=portugal",
    ).get_json()

    assert payload["positions"] == []
    assert payload["meta"]["featured_scope"] == "global"
    assert payload["featured_companies"] == [
        {
            "careers_url": "https://boards.greenhouse.io/acmebackend",
            "city": "London (United Kingdom)",
            "country": "uk",
            "country_label": "United Kingdom",
            "name": "Acme Backend Ltd",
            "visa_role_count": 1,
        }
    ]


def test_public_seo_endpoints_are_available(v2_client):
    robots = v2_client.get("/robots.txt")
    assert robots.status_code == 200
    robots_body = robots.get_data(as_text=True)
    assert "Sitemap: https://kuchup.com/sitemap.xml" in robots_body
    assert "Sitemap: https://kuchup.com/sitemap-jobs.xml" in robots_body

    sitemap = v2_client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    body = sitemap.get_data(as_text=True)
    assert "<loc>https://kuchup.com/</loc>" in body
    assert "<loc>https://kuchup.com/mcp</loc>" in body
    assert "<loc>https://kuchup.com/engineering</loc>" in body
    assert "<loc>https://kuchup.com/engineering/cant-start-new-thread</loc>" in body
    assert "<loc>https://kuchup.com/engineering/one-loop-not-faster</loc>" in body
    assert "<lastmod>" in body
    today = datetime.now(timezone.utc).date()
    for lastmod in re.findall(r"<lastmod>([^<]+)</lastmod>", body):
        assert datetime.strptime(lastmod, "%Y-%m-%d").date() <= today

    llms = v2_client.get("/llms.txt")
    assert llms.status_code == 200
    assert "kuchup.com" in llms.get_data(as_text=True).lower()

    favicon = v2_client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert "public" in (favicon.headers.get("Cache-Control") or "")

    logo = v2_client.get("/logo.png")
    assert logo.status_code == 200
    assert "public" in (logo.headers.get("Cache-Control") or "")


def test_og_default_image_is_served(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    html_dir.mkdir()
    (html_dir / "og-default.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    og = v2_client.get("/og-default.png")
    assert og.status_code == 200
    assert "public" in (og.headers.get("Cache-Control") or "")


def test_marketing_and_panel_cache_headers(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    html_dir.mkdir()
    (html_dir / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (html_dir / "pricing.html").write_text("<html>pricing</html>", encoding="utf-8")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    home = v2_client.get("/")
    assert home.status_code == 200
    assert "no-store" not in (home.headers.get("Cache-Control") or "")
    assert "max-age=300" in (home.headers.get("Cache-Control") or "")
    last_modified = home.headers.get("Last-Modified") or ""
    assert last_modified
    assert "2098" not in last_modified

    pricing = v2_client.get("/pricing")
    assert pricing.status_code == 200
    assert "max-age=300" in (pricing.headers.get("Cache-Control") or "")

    panel = v2_client.get("/panel")
    assert panel.status_code == 200
    assert panel.headers.get("Cache-Control") == "no-store"


def test_sitemap_lastmod_clamps_future_file_mtime(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    html_dir.mkdir()
    index = html_dir / "index.html"
    index.write_text("<html>home</html>", encoding="utf-8")
    future = datetime(2098, 12, 31, 20, 0, tzinfo=timezone.utc).timestamp()
    os.utime(index, (future, future))
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap = v2_client.get("/sitemap.xml")
    body = sitemap.get_data(as_text=True)
    assert f"<lastmod>{today}</lastmod>" in body
    assert "2098-12-31" not in body

    home = v2_client.get("/")
    assert "2098" not in (home.headers.get("Last-Modified") or "")


def test_next_assets_send_noindex_robots_tag(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    asset_dir = html_dir / "_next" / "static"
    asset_dir.mkdir(parents=True)
    (asset_dir / "font.woff2").write_bytes(b"woff")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    resp = v2_client.get("/_next/static/font.woff2")
    assert resp.status_code == 200
    assert resp.headers.get("X-Robots-Tag") == "noindex"


def test_mcp_marketing_path_serves_when_html_exists(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    html_dir.mkdir()
    (html_dir / "mcp.html").write_text("<html>mcp page</html>", encoding="utf-8")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    resp = v2_client.get("/mcp")
    assert resp.status_code == 200
    assert "mcp page" in resp.get_data(as_text=True)


def test_unknown_country_marketing_path_returns_404(v2_client):
    resp = v2_client.get("/relocation-jobs-no-such-country")
    assert resp.status_code == 404


def test_engineering_index_and_post_are_served(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    post_dir = html_dir / "engineering"
    post_dir.mkdir(parents=True)
    (html_dir / "engineering.html").write_text("<html>engineering index</html>", encoding="utf-8")
    (post_dir / "cant-start-new-thread.html").write_text(
        "<html>thread exhaustion</html>",
        encoding="utf-8",
    )
    (post_dir / "one-loop-not-faster.html").write_text(
        "<html>one loop not faster</html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    index = v2_client.get("/engineering")
    assert index.status_code == 200
    assert "engineering index" in index.get_data(as_text=True)
    assert "max-age=300" in (index.headers.get("Cache-Control") or "")

    post = v2_client.get("/engineering/cant-start-new-thread")
    assert post.status_code == 200
    assert "thread exhaustion" in post.get_data(as_text=True)
    assert "max-age=300" in (post.headers.get("Cache-Control") or "")

    after = v2_client.get("/engineering/one-loop-not-faster")
    assert after.status_code == 200
    assert "one loop not faster" in after.get_data(as_text=True)

    missing = v2_client.get("/engineering/no-such-post")
    assert missing.status_code == 404

    sitemap = v2_client.get("/sitemap.xml")
    body = sitemap.get_data(as_text=True)
    assert "<loc>https://kuchup.com/engineering</loc>" in body
    assert "<loc>https://kuchup.com/engineering/cant-start-new-thread</loc>" in body
    assert "<loc>https://kuchup.com/engineering/one-loop-not-faster</loc>" in body

    jobs = v2_client.get("/sitemap-jobs.xml")
    jobs_body = jobs.get_data(as_text=True)
    assert "/engineering" not in jobs_body


def test_engineering_index_serves_nested_index_html(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    nested = html_dir / "engineering"
    nested.mkdir(parents=True)
    (nested / "index.html").write_text("<html>nested engineering</html>", encoding="utf-8")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    resp = v2_client.get("/engineering")
    assert resp.status_code == 200
    assert "nested engineering" in resp.get_data(as_text=True)


def test_country_marketing_path_serves_exported_html(v2_client, monkeypatch, tmp_path):
    from relocation_jobs.web import server as web_server

    html_dir = tmp_path / "homepage"
    html_dir.mkdir()
    (html_dir / "relocation-jobs-armenia.html").write_text("<html>armenia</html>", encoding="utf-8")
    monkeypatch.setattr(web_server, "HOMEPAGE_STATIC", html_dir)

    missing_html = v2_client.get("/relocation-jobs-germany")
    assert missing_html.status_code == 404

    ok = v2_client.get("/relocation-jobs-armenia")
    assert ok.status_code == 200
    assert "armenia" in ok.get_data(as_text=True)

    sitemap = v2_client.get("/sitemap.xml")
    body = sitemap.get_data(as_text=True)
    assert "<loc>https://kuchup.com/relocation-jobs-armenia</loc>" in body
    assert "relocation-jobs-germany" not in body
