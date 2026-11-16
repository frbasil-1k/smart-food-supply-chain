from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from sfc_api import create_app
from sfc_api.config import Settings


def test_health_returns_the_success_envelope(client: FlaskClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.content_type == "application/json; charset=utf-8"
    assert response.headers["X-Request-ID"]

    body = response.get_json()
    assert set(body) == {"data", "meta"}
    assert body["meta"] == {}
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "sfc-api"
    assert body["data"]["version"] == "0.1.0"
    assert body["data"]["environment"] == "testing"
    assert body["data"]["timezone"] == "Asia/Kolkata"
    assert body["data"]["time"].endswith("+05:30")
    assert "Z" not in body["data"]["time"]


def test_health_does_not_require_database_configuration(client: FlaskClient) -> None:
    # The testing settings have DATABASE_URL=None; liveness must still answer.
    assert client.get("/api/health").status_code == 200


def test_health_ignores_an_unreachable_database_url() -> None:
    # A configured URL must not cause a connection attempt during Stage A.
    settings = Settings(
        environment="testing",
        secret_key="test-only-" + "d" * 40,
        timezone="Asia/Kolkata",
        log_level="DEBUG",
        database_url="mysql+pymysql://sfc_app:placeholder@127.0.0.1:1/unreachable",
        testing=True,
    )
    app: Flask = create_app(settings)

    assert app.test_client().get("/api/health").status_code == 200
