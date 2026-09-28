from __future__ import annotations

import os

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.notifications import send as push_send
from relocation_jobs.notifications import service as notifications_service


def _internal_secret_ok() -> bool:
    expected = (os.environ.get("PANEL_PUSH_NOTIFY_SECRET") or "").strip()
    if not expected:
        return False
    got = (request.headers.get("X-Push-Notify-Secret") or "").strip()
    return got == expected


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

    @app.post("/api/internal/notifications/after-country-wave")
    def api_internal_after_country_wave():
        if not _internal_secret_ok():
            return jsonify({"error": "Forbidden"}), 403
        body = request.get_json(silent=True) or {}
        country = (body.get("country") or "").strip().lower()
        fetch_run_id = body.get("fetch_run_id")
        try:
            run_id = int(fetch_run_id)
        except (TypeError, ValueError):
            return jsonify({"error": "fetch_run_id required"}), 400
        if not country:
            return jsonify({"error": "country required"}), 400
        result = notifications_service.send_after_country_wave(
            country=country,
            fetch_run_id=run_id,
        )
        return jsonify({"ok": True, **result})
