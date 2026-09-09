"""Cooperative cancellation for long-running scrape / Playwright work."""

from __future__ import annotations

import threading
from collections.abc import Callable

_thread_local = threading.local()
_cancel = {"checker": None}


class FetchCancelled(Exception):
    """Raised when the panel (or CLI) requests scrape cancellation."""


def set_cancel_checker(checker: Callable[[], bool] | None) -> None:
    _thread_local.cancel_checker = checker
    if threading.current_thread() is threading.main_thread():
        _cancel["checker"] = checker


def clear_cancel_checker() -> None:
    _thread_local.cancel_checker = None
    if threading.current_thread() is threading.main_thread():
        _cancel["checker"] = None


def is_cancel_requested() -> bool:
    checker = getattr(_thread_local, "cancel_checker", None) or _cancel["checker"]
    return bool(checker and checker())


def raise_if_cancelled() -> None:
    if is_cancel_requested():
        raise FetchCancelled()
