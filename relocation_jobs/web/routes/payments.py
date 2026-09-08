from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import login_required
from relocation_jobs.payments.service import (
    create_checkout_for_sku,
    process_nowpayments_notification,
)


def register(app):
    @app.post("/api/payments/checkout")
    @login_required
    def api_payments_checkout():
        body = request.get_json(silent=True) or {}
        sku = (body.get("sku") or body.get("pack_key") or "").strip()
        try:
            result = create_checkout_for_sku(
                g.user_id,
                sku,
                base_url=request.url_root,
            )
            app.logger.info(
                "checkout_started user_id=%s sku=%s kind=%s order_id=%s",
                g.user_id,
                result.get("sku"),
                result.get("kind"),
                result["order_id"],
            )
            return jsonify({"ok": True, **result}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

    @app.get("/api/payments/nowpayments/ipn")
    def api_nowpayments_ipn_probe():
        return jsonify({"ok": True})

    @app.post("/api/payments/nowpayments/ipn")
    def api_nowpayments_ipn():
        payload = request.get_json(silent=True) or {}
        signature = request.headers.get("x-nowpayments-sig", "")
        try:
            result = process_nowpayments_notification(payload, signature)
            app.logger.info(
                "payment_event paid=%s upgraded=%s deduplicated=%s",
                result.get("paid", False),
                result.get("upgraded", False),
                result.get("deduplicated", False),
            )
            return jsonify(result)
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 401
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            app.logger.error("payment order lookup failed: %s", exc)
            return jsonify({"error": str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
