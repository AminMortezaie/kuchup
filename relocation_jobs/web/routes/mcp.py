from __future__ import annotations

from urllib.parse import quote

from flask import Response, g, jsonify, request

from pydantic import ValidationError

from relocation_jobs.core.auth import login_required
from relocation_jobs.core.ats_constants import HTTPX_AVAILABLE
from relocation_jobs.core.panel_flags import company_fetch_enabled
from relocation_jobs.core.paths import supported_countries
from relocation_jobs.mcp import oauth_repo
from relocation_jobs.mcp import service as mcp_service
from relocation_jobs.mcp.oauth_provider import panel_display_base_url
from relocation_jobs.mcp.ports import INTERVIEW_NOTE, MASTER_RESUME, PROJECT_MASTER, SlugDocumentKind
from relocation_jobs.mcp.types import ApplicationProfile
from relocation_jobs.users.entitlements import entitlement_status


def _quota_error_response(exc: PermissionError):
    message = str(exc) or "MCP daily quota exceeded."
    soft = (
        f"{message} Higher limits will be available with Full Access when checkout launches. "
        "Contact support or an admin for early access."
    )
    return jsonify({"error": soft, "code": "mcp_quota_exceeded"}), 429


def register_slug_document_routes(app, *, prefix: str, kind: SlugDocumentKind) -> None:
    tag = prefix.strip("/").replace("/", "_").replace("-", "_")

    @login_required
    def api_list():
        items = mcp_service.list_documents(kind, user_id=g.user_id)
        return jsonify({"items": [item.model_dump() for item in items]})

    @login_required
    def api_get(slug):
        try:
            detail = mcp_service.get_document_detail(kind, slug, user_id=g.user_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(detail)

    @login_required
    def api_put(slug):
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        if content is None:
            return jsonify({"error": "content is required"}), 400
        label = (body.get("label") or "").strip()
        try:
            saved = mcp_service.save_document(
                kind,
                slug,
                str(content),
                label=label,
                user_id=g.user_id,
            )
        except PermissionError as exc:
            return _quota_error_response(exc)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, **saved})

    @login_required
    def api_pdf(slug):
        try:
            pdf_bytes, filename = mcp_service.read_document_pdf_download(
                kind,
                slug,
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        quoted = quote(filename)
        download = request.args.get("download", "").strip().lower() in ("1", "true", "yes")
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": (
                f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
            ),
        }
        return Response(pdf_bytes, mimetype="application/pdf", headers=headers)

    @login_required
    def api_render(slug):
        try:
            result = mcp_service.render_document_pdf(kind, slug, user_id=g.user_id)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not result.ok:
            return jsonify({"ok": False, "error": result.log, **result.model_dump()}), 400
        return jsonify({"ok": True, **result.model_dump()})

    api_list.__name__ = f"{tag}_list"
    api_get.__name__ = f"{tag}_get"
    api_put.__name__ = f"{tag}_put"
    api_pdf.__name__ = f"{tag}_pdf"
    api_render.__name__ = f"{tag}_render"
    app.add_url_rule(prefix, api_list.__name__, api_list, methods=["GET"])
    app.add_url_rule(f"{prefix}/<slug>", api_get.__name__, api_get, methods=["GET"])
    app.add_url_rule(f"{prefix}/<slug>", api_put.__name__, api_put, methods=["PUT"])
    app.add_url_rule(f"{prefix}/<slug>/pdf", api_pdf.__name__, api_pdf, methods=["GET"])
    app.add_url_rule(f"{prefix}/<slug>/render", api_render.__name__, api_render, methods=["POST"])


def register(app):
    @app.get("/api/mcp/connect-info")
    @login_required
    def api_mcp_connect_info():
        base = panel_display_base_url()
        mcp_url = f"{base}/mcp"
        return jsonify({
            "base_url": base,
            "mcp_url": mcp_url,
            "resource_url": mcp_url,
            "entitlements": entitlement_status(g.user_id),
        })

    @app.get("/api/mcp/tokens")
    @login_required
    def api_mcp_tokens_list():
        return jsonify({"items": oauth_repo.list_api_tokens(g.user_id)})

    @app.post("/api/mcp/tokens")
    @login_required
    def api_mcp_tokens_create():
        body = request.get_json(silent=True) or {}
        label = (body.get("label") or "").strip()
        token_id, raw = oauth_repo.create_api_token(user_id=g.user_id, label=label)
        return jsonify({
            "ok": True,
            "id": token_id,
            "token": raw,
            "label": label,
            "warning": "Copy this token now — it will not be shown again.",
        })

    @app.delete("/api/mcp/tokens/<int:token_id>")
    @login_required
    def api_mcp_tokens_revoke(token_id: int):
        ok = oauth_repo.revoke_api_token(user_id=g.user_id, token_id=token_id)
        if not ok:
            return jsonify({"error": "Token not found"}), 404
        return jsonify({"ok": True})

    @app.get("/api/mcp/profile")
    @login_required
    def api_mcp_profile_get():
        profile = mcp_service.get_application_profile(user_id=g.user_id)
        return jsonify({"profile": profile.model_dump()})

    @app.put("/api/mcp/profile")
    @login_required
    def api_mcp_profile_put():
        body = request.get_json(silent=True) or {}
        try:
            profile = ApplicationProfile(**body)
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        saved = mcp_service.save_application_profile(profile, user_id=g.user_id)
        return jsonify({"ok": True, **saved, "profile": profile.model_dump()})

    register_slug_document_routes(
        app, prefix="/api/mcp/master-resumes", kind=MASTER_RESUME,
    )
    register_slug_document_routes(
        app, prefix="/api/mcp/project-masters", kind=PROJECT_MASTER,
    )
    register_slug_document_routes(
        app, prefix="/api/mcp/interview-notes", kind=INTERVIEW_NOTE,
    )

    @app.get("/api/mcp/companies/<country>/<path:company>/applications")
    @login_required
    def api_mcp_company_applications(country: str, company: str):
        country_key = country.strip().lower()
        if country_key not in supported_countries():
            return jsonify({"error": f"Unknown country: {country}"}), 400
        try:
            payload = mcp_service.list_company_applications(
                country_key,
                company,
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(payload.model_dump())

    @app.get("/api/mcp/positions/<path:idempotency_key>/description")
    @login_required
    def api_mcp_position_description(idempotency_key: str):
        try:
            detail = mcp_service.get_position_description(idempotency_key)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(detail.model_dump())

    @app.put("/api/mcp/positions/<path:idempotency_key>/description")
    @login_required
    def api_mcp_position_description_put(idempotency_key: str):
        body = request.get_json(silent=True) or {}
        description_text = body.get("description_text")
        if description_text is None:
            return jsonify({"error": "description_text is required"}), 400
        try:
            detail = mcp_service.get_position_description(idempotency_key)
            mcp_service.update_position(
                detail.country,
                detail.company,
                detail.url,
                description_text=str(description_text),
            )
            updated = mcp_service.get_position_description(idempotency_key)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(updated.model_dump())

    @app.post("/api/mcp/positions/<path:idempotency_key>/fetch-description")
    @login_required
    def api_mcp_position_fetch_description(idempotency_key: str):
        if not company_fetch_enabled():
            return jsonify({
                "error": (
                    "Company fetch is disabled on this host. "
                    "Set PANEL_COMPANY_FETCH_ENABLED=1 or PANEL_SCRAPE_ENABLED=1."
                ),
            }), 503
        if not HTTPX_AVAILABLE:
            return jsonify({"error": "httpx is not installed. Run: pip install httpx"}), 503
        try:
            detail = mcp_service.fetch_and_store_position_description(idempotency_key)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(detail.model_dump())

    @app.get("/api/mcp/applications/<path:idempotency_key>")
    @login_required
    def api_mcp_application_detail(idempotency_key: str):
        try:
            detail = mcp_service.get_application_detail(idempotency_key, user_id=g.user_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(detail.model_dump())

    @app.get("/api/mcp/applications/<path:idempotency_key>/tex")
    @login_required
    def api_mcp_application_tex(idempotency_key: str):
        try:
            detail = mcp_service.read_application_tex(idempotency_key, user_id=g.user_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(detail.model_dump())

    @app.put("/api/mcp/applications/<path:idempotency_key>/tex")
    @login_required
    def api_mcp_application_tex_put(idempotency_key: str):
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        if content is None:
            return jsonify({"error": "content is required"}), 400
        try:
            saved = mcp_service.save_application_tex(
                idempotency_key,
                str(content),
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(saved)

    @app.get("/api/mcp/applications/<path:idempotency_key>/pdf")
    @login_required
    def api_mcp_application_pdf(idempotency_key: str):
        try:
            pdf_bytes, filename = mcp_service.read_application_pdf_download(
                idempotency_key,
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        quoted = quote(filename)
        download = request.args.get("download", "").strip().lower() in ("1", "true", "yes")
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": (
                f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
            ),
        }
        return Response(pdf_bytes, mimetype="application/pdf", headers=headers)

    @app.post("/api/mcp/applications/<path:idempotency_key>/render")
    @login_required
    def api_mcp_application_render(idempotency_key: str):
        try:
            result = mcp_service.render_application_pdf(idempotency_key, user_id=g.user_id)
        except PermissionError as exc:
            return _quota_error_response(exc)
        if not result.ok:
            return jsonify({"ok": False, "error": result.log, **result.model_dump()}), 400
        return jsonify({"ok": True, **result.model_dump()})

    @app.get("/api/mcp/applications/<path:idempotency_key>/cover-letter/tex")
    @login_required
    def api_mcp_application_cover_letter_tex(idempotency_key: str):
        try:
            detail = mcp_service.read_application_cover_letter_tex(
                idempotency_key, user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(detail.model_dump())

    @app.put("/api/mcp/applications/<path:idempotency_key>/cover-letter/tex")
    @login_required
    def api_mcp_application_cover_letter_tex_put(idempotency_key: str):
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        if content is None:
            return jsonify({"error": "content is required"}), 400
        try:
            saved = mcp_service.save_application_cover_letter_tex(
                idempotency_key,
                str(content),
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(saved)

    @app.get("/api/mcp/applications/<path:idempotency_key>/cover-letter/pdf")
    @login_required
    def api_mcp_application_cover_letter_pdf(idempotency_key: str):
        try:
            pdf_bytes, filename = mcp_service.read_application_cover_letter_pdf_download(
                idempotency_key,
                user_id=g.user_id,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        quoted = quote(filename)
        download = request.args.get("download", "").strip().lower() in ("1", "true", "yes")
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": (
                f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
            ),
        }
        return Response(pdf_bytes, mimetype="application/pdf", headers=headers)

    @app.post("/api/mcp/applications/<path:idempotency_key>/cover-letter/render")
    @login_required
    def api_mcp_application_cover_letter_render(idempotency_key: str):
        result = mcp_service.render_application_cover_letter_pdf(
            idempotency_key, user_id=g.user_id,
        )
        if not result.ok:
            return jsonify({"ok": False, "error": result.log, **result.model_dump()}), 400
        return jsonify({"ok": True, **result.model_dump()})
