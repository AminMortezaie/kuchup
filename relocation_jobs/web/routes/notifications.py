from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.notifications import send as push_send
from relocation_jobs.notifications import service as notifications_service


def register(app):
    @app.get("/api/notifications/vapid-public-key")
    @login_required
    def api_notifications_vapid_public_key():
        key = push_send.vapid_public_key()
        if not key:
            return jsonify({"error": "Web Push is not configured"}), 503
        return jsonify({"public_key": key})

    @app.post("/api/notifications/subscribe")
    @login_required
    def api_notifications_subscribe():
        body = request.get_json(silent=True) or {}
        try:
            notifications_service.save_subscription(g.user_id, body)
            return jsonify({"ok": True})
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/notifications/unsubscribe")
    @login_required
    def api_notifications_unsubscribe():
        body = request.get_json(silent=True) or {}
        removed = notifications_service.remove_subscription(g.user_id, body)
        return jsonify({"ok": True, "removed": removed})
