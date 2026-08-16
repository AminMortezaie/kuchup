from __future__ import annotations

from flask import jsonify

from relocation_jobs.core.health import build_health


def register(app):
    @app.get("/api/health")
    def api_health():
        body, status = build_health()
        return jsonify(body), status
