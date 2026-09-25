from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.panel.application_queue import (
    count_application_states,
    list_application_queue_positions,
    list_applied_positions,
    list_rejected_positions,
)


def _country_arg() -> str | None:
    return (request.args.get("country") or "").strip().lower() or None


def _page_args() -> tuple[int, int | None]:
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", type=int)
    return page, page_size


def register(app):
    @app.get("/api/applications/counts")
    @login_required
    def api_applications_counts():
        counts = count_application_states(g.user_id, country=_country_arg())
        return jsonify(counts)

    @app.get("/api/applications/queue")
    @login_required
    def api_applications_queue():
        page, page_size = _page_args()
        payload = list_application_queue_positions(
            g.user_id,
            country=_country_arg(),
            page=page,
            page_size=page_size,
        )
        return jsonify(payload)

    @app.get("/api/applications/applied")
    @login_required
    def api_applications_applied():
        page, page_size = _page_args()
        payload = list_applied_positions(
            g.user_id,
            country=_country_arg(),
            page=page,
            page_size=page_size,
        )
        return jsonify(payload)

    @app.get("/api/applications/rejected")
    @login_required
    def api_applications_rejected():
        page, page_size = _page_args()
        payload = list_rejected_positions(
            g.user_id,
            country=_country_arg(),
            page=page,
            page_size=page_size,
        )
        return jsonify(payload)
