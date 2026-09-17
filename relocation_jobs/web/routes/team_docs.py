from __future__ import annotations

from flask import jsonify, request

from relocation_jobs.core.auth import admin_required
from relocation_jobs.team_docs import service as team_docs_service


def _optional_int(value):
    if value is None or value == "":
        return None
    return int(value)


def register(app):
    @app.get("/api/admin/team-docs")
    @admin_required
    def api_admin_team_docs_tree():
        return jsonify(team_docs_service.list_folder_tree())

    @app.post("/api/admin/team-docs")
    @admin_required
    def api_admin_create_team_doc():
        body = request.get_json(silent=True) or {}
        try:
            folder_id = int(body.get("folder_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "folder_id is required"}), 400
        try:
            saved = team_docs_service.create_document(
                folder_id=folder_id,
                title=str(body.get("title") or ""),
                body=body.get("body") or "",
                slug=(body.get("slug") or None),
            )
            return jsonify({"ok": True, "doc": saved}), 201
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/admin/team-docs/<int:doc_id>")
    @admin_required
    def api_admin_get_team_doc(doc_id: int):
        try:
            return jsonify({"doc": team_docs_service.get_document(doc_id)})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.patch("/api/admin/team-docs/<int:doc_id>")
    @admin_required
    def api_admin_update_team_doc(doc_id: int):
        body = request.get_json(silent=True) or {}
        try:
            saved = team_docs_service.update_document(
                doc_id,
                title=None if "title" not in body else str(body.get("title") or ""),
                body=None if "body" not in body else body.get("body"),
                slug=None if "slug" not in body else body.get("slug"),
                folder_id=_optional_int(body.get("folder_id")) if "folder_id" in body else None,
            )
            return jsonify({"ok": True, "doc": saved})
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
