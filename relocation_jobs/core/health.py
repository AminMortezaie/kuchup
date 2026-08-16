from __future__ import annotations

from relocation_jobs.core.db import ping_postgres
from relocation_jobs.core.redis_client import ping_redis, redis_enabled

_STATUS_OK = "ok"
_STATUS_FAIL = "fail"


def _redis_status() -> str:
    if not redis_enabled():
        return _STATUS_OK
    return _STATUS_OK if ping_redis() else _STATUS_FAIL


def build_health() -> tuple[dict, int]:
    postgres = _STATUS_OK if ping_postgres() else _STATUS_FAIL
    redis = _redis_status()
    ok = postgres == _STATUS_OK and redis == _STATUS_OK
    body = {
        "ok": ok,
        "postgres": postgres,
        "redis": redis,
    }
    return body, (200 if ok else 503)
