from __future__ import annotations

from flask import jsonify

from relocation_jobs.core.paths import supported_countries


def job_mutation_fields(body: dict) -> tuple[str, str, str]:
    return body.get("country", ""), body.get("company", ""), body.get("url", "")


def job_mutation_error(body: dict) -> tuple | None:
    country, company, url = job_mutation_fields(body)
    if not country or country == "all":
        return jsonify({"error": "country is required (not 'all')"}), 400
    if country not in supported_countries():
        return jsonify({"error": f"Unknown country: {country}"}), 400
    if not company or not url:
        return jsonify({"error": "company and url are required"}), 400
    return None
