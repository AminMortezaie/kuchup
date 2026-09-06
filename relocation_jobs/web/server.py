from __future__ import annotations

import os
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path

from flask import Flask, Response, redirect, request, send_from_directory

from relocation_jobs.core.auth import init_auth
from relocation_jobs.core.db import get_connection
from relocation_jobs.core.log import configure_logging
from relocation_jobs.core.paths import PROJECT_ROOT, STATIC_DIR
from relocation_jobs.db import init_db
from relocation_jobs.db.migrate import apply_v2_migrations
from relocation_jobs.scrape.aggregator_seeds import ensure_aggregator_seeds
from relocation_jobs.web.routes import register_routes

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = PROJECT_ROOT
STATIC = STATIC_DIR
HOMEPAGE_STATIC = STATIC / "homepage"

MARKETING_CACHE = "public, max-age=300, stale-while-revalidate=86400"
ICON_CACHE = "public, max-age=86400"
PRIVATE_CACHE = "no-store"

FIXED_MARKETING_PATHS = (
    "/",
    "/how-it-works",
    "/pricing",
    "/mcp",
    "/engineering",
)

PRIVATE_ROBOTS_DISALLOW = (
    "/panel",
    "/remote",
    "/admin",
    "/apply",
    "/company",
    "/api/",
)


def _public_site_url() -> str:
    return (os.environ.get("PUBLIC_SITE_URL") or "https://kuchup.com").strip().rstrip("/")


def _country_marketing_path(country_key: str) -> str:
    return f"/relocation-jobs-{country_key}"


def _country_html_exists(country_key: str) -> bool:
    return (HOMEPAGE_STATIC / f"relocation-jobs-{country_key}.html").is_file()


def _exported_country_marketing_keys() -> tuple[str, ...]:
    if not HOMEPAGE_STATIC.is_dir():
        return ()
    keys: list[str] = []
    for path in HOMEPAGE_STATIC.glob("relocation-jobs-*.html"):
        key = path.name.removeprefix("relocation-jobs-").removesuffix(".html").strip().lower()
        if key:
            keys.append(key)
    return tuple(sorted(set(keys)))


def _country_key_from_marketing_path(path: str) -> str | None:
    prefix = "/relocation-jobs-"
    if not path.startswith(prefix):
        return None
    key = path[len(prefix):].strip().lower()
    return key or None


def _is_safe_engineering_slug(slug: str) -> bool:
    if not slug or "/" in slug or "." in slug:
        return False
    return all(ch.isalnum() or ch == "-" for ch in slug) and slug[0].isalnum()


def _engineering_post_slug(path: str) -> str | None:
    prefix = "/engineering/"
    if not path.startswith(prefix):
        return None
    slug = path[len(prefix):].strip("/").lower()
    if not _is_safe_engineering_slug(slug):
        return None
    return slug


def _exported_engineering_post_paths() -> tuple[str, ...]:
    eng_dir = HOMEPAGE_STATIC / "engineering"
    if not eng_dir.is_dir():
        return ()
    paths: list[str] = []
    for html in sorted(eng_dir.glob("*.html")):
        slug = html.name.removesuffix(".html").strip().lower()
        if slug and slug != "index" and _is_safe_engineering_slug(slug):
            paths.append(f"/engineering/{slug}")
    return tuple(paths)


def public_marketing_paths() -> tuple[str, ...]:
    country_paths = tuple(
        _country_marketing_path(key)
        for key in _exported_country_marketing_keys()
    )
    return FIXED_MARKETING_PATHS + country_paths + _exported_engineering_post_paths()


def _marketing_html_path(url_path: str) -> Path | None:
    if url_path == "/":
        candidate = HOMEPAGE_STATIC / "index.html"
        return candidate if candidate.is_file() else None
    segment = url_path.strip("/")
    if not segment or ".." in segment:
        return None
    html_file = HOMEPAGE_STATIC / f"{segment}.html"
    if html_file.is_file():
        return html_file
    nested = HOMEPAGE_STATIC / segment / "index.html"
    if nested.is_file():
        return nested
    return None


def _clamped_mtime_utc(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    if mtime > now:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return mtime


def _mtime_lastmod(path: Path) -> str | None:
    stamped = _clamped_mtime_utc(path)
    if stamped is None:
        return None
    return stamped.strftime("%Y-%m-%d")


def _apply_marketing_headers(resp, html_path: Path):
    resp.headers["Cache-Control"] = MARKETING_CACHE
    stamped = _clamped_mtime_utc(html_path)
    if stamped is not None:
        resp.headers["Last-Modified"] = formatdate(stamped.timestamp(), usegmt=True)
    return resp


def _sitemap_lastmod(path: str) -> str | None:
    html = _marketing_html_path(path)
    if html is None:
        return None
    return _mtime_lastmod(html)


def _favicon_candidates() -> tuple[Path, ...]:
    return (
        STATIC / "icons" / "favicon.ico",
        HOMEPAGE_STATIC / "favicon.ico",
        STATIC / "icons" / "kuchup-bird.png",
        HOMEPAGE_STATIC / "static" / "icons" / "kuchup-bird.png",
        STATIC / "icons" / "apple-touch-icon.png",
    )


app = Flask(
    __name__,
    static_folder=str(STATIC),
    static_url_path="/static",
    template_folder=str(Path(__file__).resolve().parent / "templates"),
)
app.secret_key = os.environ.get("PANEL_SECRET_KEY", "").strip() or "dev-fallback-key"
_bootstrapped = False


def bootstrap_app() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    STATIC.mkdir(exist_ok=True)
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")
    init_db()
    configure_logging()
    apply_v2_migrations(get_connection())
    ensure_aggregator_seeds()
    init_auth(app)
    _bootstrapped = True


@app.before_request
def _ensure_bootstrapped():
    if request.endpoint == "static":
        return
    bootstrap_app()


@app.after_request
def _static_cache_control(response):
    path = request.path
    if path.startswith("/static/icons/"):
        response.headers["Cache-Control"] = ICON_CACHE
    elif path.startswith("/static/"):
        response.headers["Cache-Control"] = PRIVATE_CACHE
    return response


@app.route("/admin")
def admin_page():
    resp = send_from_directory(STATIC, "admin.html")
    resp.headers["Cache-Control"] = PRIVATE_CACHE
    return resp


@app.route("/apply")
def apply_page():
    resp = send_from_directory(STATIC, "apply.html")
    resp.headers["Cache-Control"] = PRIVATE_CACHE
    return resp


@app.route("/app")
def app_page():
    return redirect("/panel", code=301)


@app.route("/company/<country>/<path:company_slug>")
def company_workspace_page(country, company_slug):
    resp = send_from_directory(STATIC, "company.html")
    resp.headers["Cache-Control"] = PRIVATE_CACHE
    return resp


@app.route("/")
def public_home_page():
    index = HOMEPAGE_STATIC / "index.html"
    if index.is_file():
        resp = send_from_directory(HOMEPAGE_STATIC, "index.html")
        return _apply_marketing_headers(resp, index)
    fallback = STATIC / "public.html"
    resp = send_from_directory(STATIC, "public.html")
    return _apply_marketing_headers(resp, fallback)


@app.route("/_next/<path:asset_path>")
def homepage_next_assets(asset_path):
    resp = send_from_directory(HOMEPAGE_STATIC / "_next", asset_path)
    resp.headers["X-Robots-Tag"] = "noindex"
    if resp.status_code == 200:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@app.route("/icon.svg")
def homepage_icon():
    if (HOMEPAGE_STATIC / "icon.svg").is_file():
        resp = send_from_directory(HOMEPAGE_STATIC, "icon.svg")
        resp.headers["Cache-Control"] = ICON_CACHE
        return resp
    return Response(status=404)


@app.route("/og-default.png")
def homepage_og_image():
    if (HOMEPAGE_STATIC / "og-default.png").is_file():
        resp = send_from_directory(HOMEPAGE_STATIC, "og-default.png")
        resp.headers["Cache-Control"] = ICON_CACHE
        return resp
    return Response(status=404)


@app.route("/logo.png")
def homepage_logo_png():
    for folder, name in (
        (HOMEPAGE_STATIC / "static" / "icons", "kuchup-bird.png"),
        (HOMEPAGE_STATIC / "brand", "kuchup-bird.png"),
        (STATIC / "icons", "kuchup-bird.png"),
        (HOMEPAGE_STATIC, "icon.png"),
    ):
        candidate = folder / name
        if candidate.is_file():
            resp = send_from_directory(folder, name)
            resp.headers["Cache-Control"] = ICON_CACHE
            return resp
    return Response(status=404)


@app.route("/favicon.ico")
def favicon_ico():
    for candidate in _favicon_candidates():
        if candidate.is_file():
            resp = send_from_directory(candidate.parent, candidate.name)
            resp.headers["Cache-Control"] = ICON_CACHE
            return resp
    return Response(status=404)


@app.route("/brand/<path:asset_path>")
def homepage_brand_assets(asset_path):
    brand_dir = HOMEPAGE_STATIC / "brand"
    target = (brand_dir / asset_path).resolve()
    if not str(target).startswith(str(brand_dir.resolve())) or not target.is_file():
        return Response(status=404)
    resp = send_from_directory(brand_dir, asset_path)
    resp.headers["Cache-Control"] = ICON_CACHE
    return resp


@app.route("/panel")
@app.route("/remote")
def panel_page():
    resp = send_from_directory(STATIC, "index.html")
    resp.headers["Cache-Control"] = PRIVATE_CACHE
    return resp


@app.route("/preview")
def preview_page():
    return redirect("/", code=301)


@app.route("/robots.txt")
def robots_txt():
    public_site_url = _public_site_url()
    disallow_lines = "\n".join(f"Disallow: {p}" for p in PRIVATE_ROBOTS_DISALLOW)
    body = "\n".join((
        "User-agent: *",
        "Allow: /",
        disallow_lines,
        "",
        f"Sitemap: {public_site_url}/sitemap.xml",
        f"Sitemap: {public_site_url}/sitemap-jobs.xml",
        "",
    ))
    return Response(body, mimetype="text/plain")


@app.route("/llms.txt")
def llms_txt():
    path = STATIC / "llms.txt"
    if path.is_file():
        resp = send_from_directory(STATIC, "llms.txt")
        resp.headers["Cache-Control"] = MARKETING_CACHE
        resp.mimetype = "text/plain"
        return resp
    return Response(status=404)


@app.route("/sitemap.xml")
def sitemap_xml():
    public_site_url = _public_site_url()
    entries: list[str] = []
    for path in public_marketing_paths():
        lastmod = _sitemap_lastmod(path)
        lines = [f"  <url>", f"    <loc>{public_site_url}{path}</loc>"]
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
        entries.append("\n".join(lines))
    body = "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        *entries,
        "</urlset>",
        "",
    ))
    return Response(body, mimetype="application/xml")


register_routes(app)


def _is_engineering_post_path(path: str) -> bool:
    slug = _engineering_post_slug(path)
    if slug is None:
        return False
    return _marketing_html_path(f"/engineering/{slug}") is not None


def _is_marketing_path(path: str) -> bool:
    if path in FIXED_MARKETING_PATHS and path != "/":
        return True
    if _is_engineering_post_path(path):
        return True
    country_key = _country_key_from_marketing_path(path)
    if not country_key:
        return False
    return _country_html_exists(country_key)


def _marketing_404():
    not_found = HOMEPAGE_STATIC / "404.html"
    if not_found.is_file():
        resp = send_from_directory(HOMEPAGE_STATIC, "404.html")
        resp.headers["Cache-Control"] = PRIVATE_CACHE
        resp.status_code = 404
        return resp
    return Response(status=404)


@app.route("/<path:slug>")
def marketing_page(slug: str):
    path = f"/{slug}"
    if not _is_marketing_path(path):
        return _marketing_404()
    html = _marketing_html_path(path)
    if html is None:
        return _marketing_404()
    rel = html.relative_to(HOMEPAGE_STATIC).as_posix()
    resp = send_from_directory(HOMEPAGE_STATIC, rel)
    return _apply_marketing_headers(resp, html)
