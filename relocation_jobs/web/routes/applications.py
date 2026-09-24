from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.panel.application_queue import (
    list_application_queue_positions,
    list_applied_positions,
)


def register(app):
    @app.get("/api/applications/queue")
    @login_required
    def api_applications_queue():
        country = (request.args.get("country") or "").strip().lower() or None
        jobs = list_application_queue_positions(g.user_id, country=country)
        return jsonify({"jobs": jobs})

    @app.get("/api/applications/applied")
    @login_required
    def api_applications_applied():
        country = (request.args.get("country") or "").strip().lower() or None
        jobs = list_applied_positions(g.user_id, country=country)
        return jsonify({"jobs": jobs})
