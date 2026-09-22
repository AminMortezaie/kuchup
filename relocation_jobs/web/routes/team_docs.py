from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import admin_required
from relocation_jobs.team_docs import service as team_docs_service
from relocation_jobs.team_docs.markdown import drop_matching_lead_h1, render_markdown


def _with_html(doc: dict) -> dict:
    if "body" not in doc:
        return doc
    return {
        **doc,
        "html": drop_matching_lead_h1(render_markdown(doc.get("body") or ""), doc.get("title")),
    }


def register(app):
    @app.get("/api/admin/team-docs")
    @admin_required
    def api_admin_team_docs_tree():
        return jsonify(team_docs_service.list_folder_tree())

    @app.post("/api/admin/team-docs")
    @admin_required
    def api_admin_create_team_doc():
        body = request.get_json(silent=True) or {}
        folder = str(body.get("folder") or "").strip()
        if not folder:
            return jsonify({"error": "folder is required"}), 400
        try:
            saved = team_docs_service.create_document(
                folder=folder,
                title=str(body.get("title") or ""),
                body=body.get("body") or "",
                slug=(body.get("slug") or None),
                editor_user_id=g.user_id,
            )
            return jsonify({"ok": True, "doc": _with_html(saved)}), 201
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/admin/team-docs/<int:doc_id>")
    @admin_required
    def api_admin_get_team_doc(doc_id: int):
        try:
            return jsonify({"doc": _with_html(team_docs_service.get_document(doc_id))})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.patch("/api/admin/team-docs/<int:doc_id>")
    @admin_required
    def api_admin_update_team_doc(doc_id: int):
        body = request.get_json(silent=True) or {}
        folder = None
        if "folder" in body:
            folder = str(body.get("folder") or "").strip() or None
        try:
            saved = team_docs_service.update_document(
                doc_id,
                title=None if "title" not in body else str(body.get("title") or ""),
                body=None if "body" not in body else body.get("body"),
                slug=None if "slug" not in body else body.get("slug"),
                folder=folder,
                editor_user_id=g.user_id,
            )
            return jsonify({"ok": True, "doc": _with_html(saved)})
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.delete("/api/admin/team-docs/<int:doc_id>")
    @admin_required
    def api_admin_delete_team_doc(doc_id: int):
        try:
            team_docs_service.delete_document(doc_id)
            return jsonify({"ok": True})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
