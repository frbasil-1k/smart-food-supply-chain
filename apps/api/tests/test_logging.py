from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from sfc_api.config import Settings
from sfc_api.logging_config import JsonFormatter


@pytest.fixture
def captured_logs(app: Flask, settings: Settings) -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        JsonFormatter(redactions=(settings.secret_key, settings.database_url or ""))
    )
    app.logger.handlers = [handler]
    app.logger.propagate = False
    app.logger.setLevel(logging.INFO)
    yield stream


def _log_records(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def test_request_logging_is_json_and_never_logs_the_query_string(
    client: FlaskClient,
    settings: Settings,
    captured_logs: io.StringIO,
) -> None:
    response = client.get(f"/api/health?token={settings.secret_key}")

    records = _log_records(captured_logs)
    assert records
    access = next(record for record in records if record.get("event") == "request_completed")
    assert access["method"] == "GET"
    assert access["path"] == "/api/health"
    assert access["status"] == 200
    assert access["request_id"] == response.headers["X-Request-ID"]
    assert "duration_ms" in access
    assert "token=" not in captured_logs.getvalue()
    assert settings.secret_key not in captured_logs.getvalue()


def test_exception_logs_redact_configured_secrets(
    app: Flask,
    client: FlaskClient,
    settings: Settings,
    captured_logs: io.StringIO,
) -> None:
    @app.get("/api/_log-failure")
    def log_failure():
        raise RuntimeError(f"failure with secret {settings.secret_key}")

    response = client.get("/api/_log-failure")

    assert response.status_code == 500
    text = captured_logs.getvalue()
    assert settings.secret_key not in text
    assert "***" in text
    assert settings.secret_key not in response.get_data(as_text=True)


def test_formatter_redacts_common_credential_patterns() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="login failed password=hunter2 token=abc123",
        args=(),
        exc_info=None,
    )

    output = JsonFormatter().format(record)

    assert "hunter2" not in output
    assert "abc123" not in output
    assert "password=***" in output
