from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.panel.stats import compute_user_board_stats
from relocation_jobs.shared.board_contract import CATALOG_KIND_RELOCATION
from relocation_jobs.web.board_payload import build_board_payload
from relocation_jobs.web.query import query_flags


def register(app):
    @app.get("/api/board")
    @login_required
    def api_board():
        return jsonify(build_board_payload(g.user_id, catalog_kind=CATALOG_KIND_RELOCATION))

    @app.get("/api/board/stats")
    @login_required
    def api_board_stats():
        scope = query_flags()
        timezone_name = (request.args.get("timezone") or "").strip() or None
        latest_fetch_new_jobs = request.args.get("latest_fetch_new_jobs", type=int) or 0
        return jsonify(compute_user_board_stats(
            user_id=g.user_id,
            country_key=scope["country_key"],
            timezone_name=timezone_name,
            latest_fetch_new_jobs=latest_fetch_new_jobs,
        ))
