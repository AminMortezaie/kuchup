"""Reusable helpers for mocking requests.get/post in scrape tests."""

from __future__ import annotations

import json
from typing import Any


class MockResponse:
    """Minimal requests.Response stand-in."""

    def __init__(
        self,
        *,
        text: str = "",
        json_data: Any = None,
        status_code: int = 200,
        content: bytes | None = None,
        ok: bool | None = None,
        url: str = "",
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.ok = ok if ok is not None else status_code < 400
        self._json_data = json_data
        self.content = content if content is not None else text.encode("utf-8")
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.text)
