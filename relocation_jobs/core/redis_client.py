from __future__ import annotations

import functools
import os

import redis


def redis_url() -> str:
    return os.environ.get("REDIS_URL", "").strip()


def redis_enabled() -> bool:
    return bool(redis_url())


@functools.cache
def get_redis():
    if not redis_enabled():
        raise RuntimeError("REDIS_URL is not configured")
    return redis.from_url(redis_url(), decode_responses=True)


def ping_redis() -> bool:
    if not redis_enabled():
        return False
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def reset_redis_client() -> None:
    get_redis.cache_clear()
