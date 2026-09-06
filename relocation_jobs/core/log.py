from __future__ import annotations

import logging
import os
import sys

import structlog

_configured = False

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _log_level() -> int:
    name = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    return _LEVELS.get(name, logging.INFO)


def _use_json_logs() -> bool:
    raw = (os.environ.get("LOG_FORMAT") or "").strip().lower()
    if raw == "json":
        return True
    if raw == "console":
        return False
    return not sys.stderr.isatty()


def _shared_processors(*, json_logs: bool) -> list:
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    if json_logs:
        processors.append(structlog.processors.format_exc_info)
    return processors


def _install_stderr_handler(*, json_logs: bool, shared: list) -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_log_level())


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    json_logs = _use_json_logs()
    shared = _shared_processors(json_logs=json_logs)
    structlog.configure(
        processors=shared + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    _install_stderr_handler(json_logs=json_logs, shared=shared)
    _configured = True
