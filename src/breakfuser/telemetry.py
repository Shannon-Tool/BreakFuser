"""Structured tracing with content-safe operational logs."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_SECRET = re.compile(r"(?i)(bearer\s+|api[_-]?key[=:]\s*|sk-)[a-z0-9._\-/+=]+")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def redact(text: str) -> str:
    return _EMAIL.sub("[redacted-email]", _SECRET.sub("[redacted-secret]", text))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Trace:
    def __init__(
        self,
        trace_id: str | None = None,
        logger_name: str = "breakfuser",
        log_level: str = "INFO",
    ) -> None:
        self.id = trace_id or uuid.uuid4().hex
        self.events: list[dict[str, Any]] = []
        self._logger = logging.getLogger(logger_name)
        self.log_level = log_level.upper()
        levels = logging.getLevelNamesMapping()
        if self.log_level not in levels:
            raise ValueError(f"Invalid trace log level: {log_level!r}")
        self._level = levels[self.log_level]

    def record(self, stage: str, **metadata: Any) -> None:
        safe = {
            key: redact(value) if isinstance(value, str) else value
            for key, value in metadata.items()
            if key not in {"api_key", "prompt", "response", "raw_content"}
        }
        event = {"trace_id": self.id, "stage": stage, "timestamp": time.time(), **safe}
        self.events.append(event)
        self._logger.log(self._level, json.dumps(event, default=str))

    @contextmanager
    def span(self, stage: str, **metadata: Any) -> Iterator[None]:
        started = time.perf_counter()
        self.record(f"{stage}.start", **metadata)
        try:
            yield
        finally:
            self.record(f"{stage}.end", latency_ms=round((time.perf_counter() - started) * 1000, 3))
