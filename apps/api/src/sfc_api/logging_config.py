"""Structured, redacting logs and request correlation.

The API logs request metadata only: method, path, status, duration and request
ID. Bodies, headers, cookies, credentials and query strings are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from flask import Flask, Response, g, has_request_context, request

from .config import Settings

_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|token|cookie|authorization|api[_-]?key)\b"
    r"(\s*[=:]\s*)[^\s,;]+"
)
_ALLOWED_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status",
    "duration_ms",
    "user_id",
    "operator",
    "record_count",
    "invocation_id",
)


def _redact_text(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return _KEY_VALUE_PATTERN.sub(r"\1\2***", text)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line with only allow-listed metadata."""

    def __init__(self, redactions: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.redactions = redactions

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_text(record.getMessage(), self.redactions),
        }

        if has_request_context():
            request_id = g.get("request_id")
            if request_id:
                payload["request_id"] = request_id

        for field in _ALLOWED_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = _redact_text(
                self.formatException(record.exc_info),
                self.redactions,
            )

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(app: Flask, settings: Settings) -> None:
    level = getattr(logging, settings.log_level)
    redactions = tuple(
        value
        for value in (
            settings.secret_key,
            settings.database_url,
            settings.database_password,
            settings.ops_database_url,
            settings.ops_database_password,
        )
        if value
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter(redactions=redactions))

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    app.logger.propagate = False


def register_request_logging(app: Flask) -> None:
    @app.before_request
    def begin_request() -> None:
        g.request_id = uuid4().hex
        g.request_started_at = perf_counter()

    @app.after_request
    def finish_request(response: Response) -> Response:
        request_id = g.get("request_id")
        if request_id:
            response.headers["X-Request-ID"] = request_id

        started_at = g.get("request_started_at")
        duration_ms = (
            round((perf_counter() - started_at) * 1000, 2) if started_at is not None else None
        )
        app.logger.info(
            "Request completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
