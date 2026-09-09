from __future__ import annotations

import os
from html import escape
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from relocation_jobs.mcp import oauth_repo
from relocation_jobs.users.repo import get_user_by_id

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} — Kuchup MCP</title>
  <style>
    :root {{ color-scheme: light; --ink: #0e3a69; --muted: #5d7488; --line: #a9c1d1; --paper: #fcfaf7; --accent: #ff6b35; --accent-ink: #082743; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Manrope, "Segoe UI", system-ui, sans-serif; background: linear-gradient(160deg, #f2f7fa, #fcfaf7 55%, #fff); color: var(--ink); min-height: 100vh; display: grid; place-items: center; padding: 24px; }}
    .card {{ width: min(420px, 100%); background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 28px; box-shadow: 0 8px 24px rgba(14, 58, 105, 0.10); }}
    h1 {{ margin: 0 0 8px; font-size: 1.35rem; font-family: Lexend, sans-serif; }}
    p {{ margin: 0 0 18px; color: var(--muted); line-height: 1.45; font-size: 0.95rem; }}
    a.primary {{ display: block; text-align: center; text-decoration: none; width: 100%; border: 0; border-radius: 999px; padding: 12px 14px; background: var(--accent); color: var(--accent-ink); font: inherit; font-weight: 600; }}
    a.secondary {{ display: block; text-align: center; text-decoration: none; width: 100%; margin-top: 10px; border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; background: #fff; color: var(--muted); font: inherit; font-weight: 600; }}
    .scopes {{ margin: 0 0 16px; padding-left: 1.1rem; color: var(--muted); font-size: 0.9rem; line-height: 1.45; }}
    .error {{ background: #fdecec; color: #8a1f1f; border: 1px solid #f3c1c1; border-radius: 10px; padding: 10px 12px; margin-bottom: 14px; font-size: 0.9rem; }}
    .brand {{ font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); font-weight: 700; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">Kuchup</div>
    <h1>{heading}</h1>
    <p>{message}</p>
    {error}
    {body}
  </div>
</body>
</html>
"""


def _panel_google_start_url(request_id: str) -> str:
    panel = (os.environ.get("PANEL_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not panel:
        panel = "https://kuchup.com"
    query = urlencode({"mcp_request_id": request_id, "next": "/panel"})
    return f"{panel}/api/auth/google?{query}"


def _page(*, title: str, heading: str, message: str, body: str, error: str = "") -> HTMLResponse:
    err = f'<div class="error">{escape(error)}</div>' if error else ""
    html = _PAGE.format(
        title=escape(title),
        heading=escape(heading),
        message=message,
        error=err,
        body=body,
    )
    return HTMLResponse(html)


async def oauth_login_get(request: Request) -> HTMLResponse:
    request_id = (request.query_params.get("request_id") or "").strip()
    pending = oauth_repo.get_pending_request(request_id) if request_id else None
    if pending is None:
        return _page(
            title="Expired",
            heading="Authorization expired",
            message="Start again from Claude or Cursor — this login link is no longer valid.",
            body="",
        )
    google_url = escape(_panel_google_start_url(request_id))
    deny_url = escape(f"/oauth/deny?request_id={request_id}")
    body = f"""
    <p>Signing in allows Claude or Cursor to use your Kuchup application data for this account only.</p>
    <ul class="scopes">
      <li>Read your board queue and job context</li>
      <li>Read and write resumes, project masters, and tailored PDFs</li>
      <li>Update application tracking when you ask</li>
    </ul>
    <a class="primary" href="{google_url}">Allow — Continue with Google</a>
    <a class="secondary" href="{deny_url}">Deny</a>
    """
    return _page(
        title="Connect",
        heading="Connect AI",
        message="Review access, then allow or deny this client.",
        body=body,
    )


async def oauth_deny_get(request: Request) -> HTMLResponse:
    request_id = (request.query_params.get("request_id") or "").strip()
    if request_id:
        oauth_repo.delete_pending_request(request_id)
    return _page(
        title="Denied",
        heading="Access denied",
        message="You denied this MCP client. You can close this window and return to Claude or Cursor.",
        body="",
    )


async def oauth_login_post(request: Request) -> HTMLResponse | RedirectResponse:
    request_id = (request.query_params.get("request_id") or "").strip()
    if not request_id:
        form = await request.form()
        request_id = str(form.get("request_id") or "").strip()
    if not request_id:
        return _page(
            title="Expired",
            heading="Authorization expired",
            message="Start again from Claude or Cursor — this login link is no longer valid.",
            body="",
        )
    return RedirectResponse(url=_panel_google_start_url(request_id), status_code=302)


async def oauth_health(_request: Request) -> HTMLResponse:
    return HTMLResponse("ok")


def username_for_subject(subject: str | None) -> str:
    if not subject:
        return ""
    user = get_user_by_id(int(subject)) or {}
    return (user.get("username") or "").strip()
