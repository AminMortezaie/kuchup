from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.core.paths import supported_countries
from relocation_jobs.catalog.locations import list_company_locations
from relocation_jobs.panel.stats import compute_user_board_stats
from relocation_jobs.remote.countries import list_remote_ats_types, list_remote_countries
from relocation_jobs.shared.board_contract import (
    CATALOG_KIND_REMOTE,
    is_remote_country_key,
)
from relocation_jobs.web.board_payload import build_board_payload
from relocation_jobs.web.query import query_flags


def register(app):
    @app.get("/api/remote/board")
    @login_required
    def api_remote_board():
        scope = query_flags()
        country_key = scope["country_key"]
        if country_key and not is_remote_country_key(country_key):
            return jsonify({"error": f"Unknown remote board: {country_key}"}), 400
        return jsonify(build_board_payload(g.user_id, catalog_kind=CATALOG_KIND_REMOTE))

    @app.get("/api/remote/board/stats")
    @login_required
    def api_remote_board_stats():
        scope = query_flags()
        country_key = scope["country_key"]
        if country_key and not is_remote_country_key(country_key):
            return jsonify({"error": f"Unknown remote board: {country_key}"}), 400
        timezone_name = (request.args.get("timezone") or "").strip() or None
        latest_fetch_new_jobs = request.args.get("latest_fetch_new_jobs", type=int) or 0
        return jsonify(compute_user_board_stats(
            user_id=g.user_id,
            country_key=country_key,
            timezone_name=timezone_name,
            latest_fetch_new_jobs=latest_fetch_new_jobs,
        ))

    @app.get("/api/remote/countries")
    @login_required
    def api_remote_countries():
        return jsonify(list_remote_countries())

    @app.get("/api/remote/ats-types")
    @login_required
    def api_remote_ats_types():
        return jsonify({"ats_types": list_remote_ats_types()})

    @app.get("/api/remote/locations")
    @login_required
    def api_remote_locations():
        country = request.args.get("country", "all")
        country_key = country if country != "all" else None
        if country_key and not is_remote_country_key(country_key):
            return jsonify({"error": f"Unknown remote board: {country}"}), 400
        if country_key and country_key not in supported_countries():
            return jsonify({"error": f"Unknown country: {country}"}), 400
        for_picker = request.args.get("picker", "").lower() in ("1", "true", "yes")
        if country_key:
            locations = list_company_locations(country_key, for_picker=for_picker)
        else:
            locations = []
            for key in sorted(supported_countries()):
                if is_remote_country_key(key):
                    locations.extend(list_company_locations(key, for_picker=for_picker))
        return jsonify({"locations": locations})
