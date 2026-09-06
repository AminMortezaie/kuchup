from __future__ import annotations

from relocation_jobs.credits.types import CreditOperation, CreditPack


MONTHLY_FREE_CREDITS = 30

OPERATION_COSTS: dict[CreditOperation, int] = {
    CreditOperation.ROLE_REPLACEMENT: 1,
    CreditOperation.PDF_RENDER: 1,
    CreditOperation.JOB_DESCRIPTION_FETCH: 1,
    CreditOperation.APPLICATION_PACK: 5,
    CreditOperation.COMPANY_REFRESH: 5,
    CreditOperation.PUBLIC_JOB_SAVE: 1,
}

PACKS: tuple[CreditPack, ...] = (
    CreditPack("starter", 50, 499, "USD", "50 credits"),
    CreditPack("plus", 150, 1199, "USD", "150 credits"),
    CreditPack("power", 400, 2499, "USD", "400 credits"),
)


def operation_cost(operation: CreditOperation) -> int:
    return OPERATION_COSTS[operation]


def list_credit_packs() -> list[dict]:
    return [pack.as_dict() for pack in PACKS]


def credit_pack(pack_key: str) -> CreditPack:
    key = pack_key.strip().lower()
    for pack in PACKS:
        if pack.key == key:
            return pack
    raise LookupError(f"Unknown credit pack: {pack_key}")
