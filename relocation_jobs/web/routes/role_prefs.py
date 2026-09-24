from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import admin_required, login_required
from relocation_jobs.roles import service as role_service


def register(app):
    @app.get("/api/role-preferences")
    @login_required
    def api_role_preferences():
        return jsonify({"tags": role_service.list_preferences(g.user_id)})

    @app.put("/api/role-preferences/<int:tag_id>")
    @login_required
    def api_set_role_preference(tag_id: int):
        body = request.get_json(silent=True) or {}
        if "enabled" not in body:
            return jsonify({"error": "enabled is required"}), 400
        try:
            tag = role_service.set_tag_enabled(g.user_id, tag_id, bool(body.get("enabled")))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify({"tag": tag})

    @app.post("/api/admin/role-filter-tags")
    @admin_required
    def api_admin_add_role_filter_tag():
        body = request.get_json(silent=True) or {}
        try:
            tag = role_service.add_tag(body.get("keyword") or "", body.get("kind") or "")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"tag": tag}), 201

    @app.patch("/api/admin/role-filter-tags/<int:tag_id>")
    @admin_required
    def api_admin_edit_role_filter_tag(tag_id: int):
        body = request.get_json(silent=True) or {}
        try:
            tag = role_service.edit_tag(
                tag_id,
                body.get("keyword") or "",
                body.get("kind") or "",
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify({"tag": tag})
