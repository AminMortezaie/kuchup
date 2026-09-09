from __future__ import annotations

import logging

import structlog

from relocation_jobs.core.log import configure_logging

LOGGER_NAME = "relocation_jobs.fetch"


def log_event(message: str, *, level: int = logging.INFO, **context) -> None:
    configure_logging()
    extra = {key: value for key, value in context.items() if value is not None}
    structlog.get_logger(LOGGER_NAME).bind(**extra).log(level, message)
