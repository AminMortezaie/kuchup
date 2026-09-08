from __future__ import annotations

from relocation_jobs.credits.policy import credit_pack
from relocation_jobs.payments.types import (
    ORDER_KIND_CREDITS,
    ORDER_KIND_FULL_ACCESS,
    CheckoutSku,
)


FULL_ACCESS_SKU = CheckoutSku(
    key="full_access",
    kind=ORDER_KIND_FULL_ACCESS,
    credits=0,
    price_minor=2900,
    currency="USD",
    label="Full Access",
)


def sku_for_checkout(sku_key: str) -> CheckoutSku:
    key = sku_key.strip().lower()
    if key == FULL_ACCESS_SKU.key:
        return FULL_ACCESS_SKU
    pack = credit_pack(key)
    return CheckoutSku(
        key=pack.key,
        kind=ORDER_KIND_CREDITS,
        credits=pack.credits,
        price_minor=pack.price_minor,
        currency=pack.currency,
        label=pack.label,
    )
