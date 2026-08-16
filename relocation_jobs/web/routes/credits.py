from __future__ import annotations

from flask import g, jsonify, request

from relocation_jobs.core.auth import admin_required, login_required
from relocation_jobs.credits import repo as credits_repo
from relocation_jobs.credits.policy import list_credit_packs
from relocation_jobs.credits.service import grant_admin_credits, wallet_status
from relocation_jobs.payments.service import (
    create_credit_checkout,
    process_nowpayments_notification,
    reconcile_order,
    revoke_order_credits,
)


def register(app):
    @app.get("/api/credits/packs")
    def api_credit_packs():
        return jsonify({"packs": list_credit_packs()})

    @app.get("/api/credits")
    @login_required
    def api_credits():
        include_history = request.args.get("history", "").lower() in ("1", "true", "yes")
        return jsonify(wallet_status(g.user_id, include_history=include_history))

    @app.post("/api/credits/checkout")
    @login_required
    def api_credit_checkout():
        body = request.get_json(silent=True) or {}
        try:
            result = create_credit_checkout(
                g.user_id,
                (body.get("pack_key") or "").strip(),
                base_url=request.url_root,
            )
            app.logger.info(
                "credit_checkout_started user_id=%s pack=%s order_id=%s",
                g.user_id,
                (body.get("pack_key") or "").strip(),
                result["order_id"],
            )
            return jsonify({"ok": True, **result}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

    @app.get("/api/credits/orders/<int:order_id>")
    @login_required
    def api_credit_order(order_id: int):
        order = credits_repo.get_order(order_id, user_id=g.user_id)
        if not order:
            return jsonify({"error": "Credit order not found"}), 404
        return jsonify({"order": order})

    @app.post("/api/payments/nowpayments/ipn")
    def api_nowpayments_ipn():
        payload = request.get_json(silent=True) or {}
        signature = request.headers.get("x-nowpayments-sig", "")
        try:
            result = process_nowpayments_notification(payload, signature)
            app.logger.info(
                "credit_payment_event paid=%s deduplicated=%s",
                result.get("paid", False),
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

    @app.post("/api/admin/users/<int:user_id>/credits")
    @admin_required
    def api_admin_grant_credits(user_id: int):
        body = request.get_json(silent=True) or {}
        try:
            credits = int(body.get("credits"))
            result = grant_admin_credits(
                user_id,
                credits=credits,
                reason=(body.get("reason") or "").strip(),
            )
            app.logger.info(
                "credit_admin_grant admin_id=%s user_id=%s credits=%s",
                g.user_id,
                user_id,
                credits,
            )
            return jsonify({
                "ok": True,
                "wallet": result,
            })
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.get("/api/admin/credit-orders")
    @admin_required
    def api_admin_credit_orders():
        return jsonify({"orders": credits_repo.list_orders_for_admin()})

    @app.get("/api/admin/credits/audit")
    @admin_required
    def api_admin_credit_audit():
        return jsonify(credits_repo.credit_audit())

    @app.post("/api/admin/credit-orders/<int:order_id>/reconcile")
    @admin_required
    def api_admin_reconcile_credit_order(order_id: int):
        try:
            return jsonify({"ok": True, **reconcile_order(order_id)})
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @app.post("/api/admin/credit-orders/<int:order_id>/revoke")
    @admin_required
    def api_admin_revoke_credit_order(order_id: int):
        body = request.get_json(silent=True) or {}
        try:
            return jsonify({
                "ok": True,
                **revoke_order_credits(
                    order_id,
                    reason=(body.get("reason") or "").strip(),
                ),
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
