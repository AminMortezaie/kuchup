from __future__ import annotations

import json
import logging
import os
from typing import Any

import structlog

from relocation_jobs.core.log import configure_logging

LOGGER_NAME = "relocation_jobs.fetch"


def _body_preview_limit() -> int:
    raw = (os.environ.get("FETCH_LOG_BODY_LIMIT") or "2000").strip()
    try:
        return max(200, min(int(raw), 20000))
    except (TypeError, ValueError):
        return 2000


def configure_fetch_logging() -> None:
    configure_logging()


def bind_fetch_log_context(**fields) -> None:
    cleaned = {key: value for key, value in fields.items() if value is not None}
    if cleaned:
        structlog.contextvars.bind_contextvars(**cleaned)


def get_fetch_log_context() -> dict:
    return dict(structlog.contextvars.get_contextvars())


def _preview_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, (dict, list)):
        try:
            text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            text = str(body)
    elif isinstance(body, (bytes, bytearray)):
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            return f"<bytes len={len(body)}>"
    else:
        text = str(body)
    collapsed = " ".join(text.split())
    limit = _body_preview_limit()
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}…({len(collapsed)} chars)"


def _optional_preview(body: Any) -> str | None:
    if body is None or not str(body).strip():
        return None
    return _preview_body(body)


def log_event(message: str, *, level: int = logging.INFO, **context) -> None:
    configure_logging()
    extra = {key: value for key, value in context.items() if value is not None}
    structlog.get_logger(LOGGER_NAME).bind(**extra).log(level, message)


def log_http_exchange(
    *,
    kind: str,
    method: str,
    url: str,
    job_url: str | None = None,
    job_title: str | None = None,
    request_body: Any = None,
    response_status: int | None = None,
    response_body: Any = None,
    response_bytes: int | None = None,
    error: str | None = None,
    level: int = logging.INFO,
    **context,
) -> None:
    label = {
        "board": "job board list",
        "job": "job posting",
        "http": "http",
    }.get(kind, kind)
    fields: dict[str, Any] = {
        "http_kind": kind,
        "method": method.upper(),
        "url": url,
        "job_url": job_url,
        "job_title": job_title,
        "request_body": _optional_preview(request_body),
        "error": error,
        **context,
    }
    if error is None:
        fields["response_status"] = response_status
        fields["response_bytes"] = response_bytes
        fields["response_body"] = _optional_preview(response_body)
    log_event(f"HTTP {method.upper()} {label}", level=level, **fields)
