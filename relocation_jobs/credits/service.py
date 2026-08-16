from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from relocation_jobs.credits import repo
from relocation_jobs.credits.policy import (
    MONTHLY_FREE_CREDITS,
    credit_pack,
    list_credit_packs,
    operation_cost,
)
from relocation_jobs.credits.types import (
    CreditBalance,
    CreditGrantKind,
    CreditOperation,
)
from relocation_jobs.users.entitlements import plan_is_full_access
from relocation_jobs.users.repo import get_user_by_id


def _period_bounds(now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now(timezone.utc)
    period = current.strftime("%Y-%m")
    if current.month == 12:
        next_month = current.replace(
            year=current.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0,
        )
    else:
        next_month = current.replace(
            month=current.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0,
        )
    return period, next_month.isoformat()


def ensure_monthly_grant(user_id: int) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        raise LookupError("User not found")
    if plan_is_full_access(user.get("plan"), user_id=user_id):
        return False
    period, expires_at = _period_bounds()
    return repo.create_grant(
        user_id,
        kind=CreditGrantKind.MONTHLY,
        source_key=f"monthly:{period}",
        credits=MONTHLY_FREE_CREDITS,
        expires_at=expires_at,
        metadata={"period_key": period},
    )


def credit_balance(user_id: int) -> CreditBalance:
    ensure_monthly_grant(user_id)
    repo.expire_grants(user_id)
    promotional, purchased = repo.balance_totals(user_id)
    period, next_reset = _period_bounds()
    return CreditBalance(
        promotional=promotional,
        purchased=purchased,
        total=promotional + purchased,
        next_reset_at=next_reset,
        period_key=period,
    )


def wallet_status(user_id: int, *, include_history: bool = False) -> dict:
    balance = credit_balance(user_id)
    result = {
        "balance": balance.as_dict(),
        "packs": list_credit_packs(),
    }
    if include_history:
        result["ledger"] = repo.list_ledger(user_id)
        result["orders"] = repo.list_orders(user_id)
    return result


def spend_for_operation(
    user_id: int,
    operation: CreditOperation,
    *,
    idempotency_key: str,
    metadata: dict | None = None,
) -> dict:
    ensure_monthly_grant(user_id)
    repo.expire_grants(user_id)
    return repo.spend_credits(
        user_id,
        cost=operation_cost(operation),
        operation=operation.value,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def refund_operation(user_id: int, *, spend_key: str, reason: str) -> bool:
    return repo.refund_spend(user_id, spend_key=spend_key, reason=reason)


def usage_migration_done(user_id: int, period_key: str) -> bool:
    return repo.usage_migration_done(user_id, period_key)


def mark_usage_migration_done(user_id: int, period_key: str) -> None:
    repo.mark_usage_migration_done(user_id, period_key)


def grant_admin_credits(user_id: int, *, credits: int, reason: str) -> dict:
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("A reason is required")
    source_key = f"admin:{user_id}:{uuid4().hex}"
    repo.create_grant(
        user_id,
        kind=CreditGrantKind.ADMIN,
        source_key=source_key,
        credits=credits,
        expires_at=None,
        metadata={"reason": clean_reason},
    )
    return wallet_status(user_id, include_history=True)


def grant_order_credits(order: dict) -> bool:
    return repo.create_grant(
        int(order["user_id"]),
        kind=CreditGrantKind.PURCHASED,
        source_key=f"order:{order['provider']}:{order['provider_order_id']}",
        credits=int(order["credits"]),
        expires_at=None,
        metadata={
            "order_id": int(order["id"]),
            "pack_key": order["pack_key"],
            "price_minor": int(order["price_minor"]),
            "currency": order["currency"],
        },
    )


def pack_for_checkout(pack_key: str):
    return credit_pack(pack_key)
