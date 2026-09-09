from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.opportunities.service import save_preferences_and_refresh, visible_preferences


def _preferences_payload(prefs) -> dict:
    return {
        "target_countries": list(prefs.target_countries),
        "seniority": prefs.seniority,
        "keywords": list(prefs.keywords),
        "remote_ok": prefs.remote_ok,
        "preferences_confirmed": bool(prefs.preferences_confirmed),
    }


def register(app):
    @app.get("/api/preferences")
    @login_required
    def api_get_preferences():
        prefs = visible_preferences(g.user_id)
        return jsonify({"preferences": _preferences_payload(prefs)})

    @app.put("/api/preferences")
    @login_required
    def api_put_preferences():
        body = request.get_json(silent=True) or {}
        countries = body.get("target_countries")
        if not isinstance(countries, list) or not countries:
            return jsonify({"error": "target_countries must be a non-empty list"}), 400
        keywords = body.get("keywords") or []
        if not isinstance(keywords, list):
            return jsonify({"error": "keywords must be a list"}), 400
        result = save_preferences_and_refresh(
            g.user_id,
            target_countries=[str(c) for c in countries],
            seniority=str(body.get("seniority") or ""),
            keywords=[str(k) for k in keywords],
            remote_ok=bool(body.get("remote_ok")),
        )
        return jsonify({"ok": True, **result})
