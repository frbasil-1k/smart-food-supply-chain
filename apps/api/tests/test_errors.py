from __future__ import annotations

from flask import Flask, request
from flask.testing import FlaskClient
from pydantic import Field

from sfc_api.config import Settings
from sfc_api.responses import success
from sfc_api.validation import StrictModel, parse_json


class ProbePayload(StrictModel):
    quantity: int = Field(gt=0)


def test_not_found_uses_the_error_envelope(client: FlaskClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.content_type == "application/json; charset=utf-8"

    body = response.get_json()
    assert set(body) == {"error", "request_id"}
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]
    assert "details" not in body["error"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "Traceback" not in response.get_data(as_text=True)


def test_method_not_allowed_uses_the_error_envelope(client: FlaskClient) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "malformed_request"
    assert response.headers["X-Request-ID"]


def test_validation_errors_are_returned_as_422_details(
    app: Flask,
    client: FlaskClient,
) -> None:
    @app.post("/api/_validation-probe")
    def validation_probe():
        payload = parse_json(ProbePayload, request.get_json(silent=True))
        return success(payload.model_dump())

    valid = client.post("/api/_validation-probe", json={"quantity": 3})
    assert valid.status_code == 200
    assert valid.get_json()["data"] == {"quantity": 3}

    invalid = client.post(
        "/api/_validation-probe",
        json={"quantity": 0, "unexpected": "field"},
    )
    assert invalid.status_code == 422

    body = invalid.get_json()
    assert body["error"]["code"] == "validation_error"
    fields = {detail["field"] for detail in body["error"]["details"]}
    assert "quantity" in fields
    assert "unexpected" in fields
    assert body["request_id"] == invalid.headers["X-Request-ID"]


def test_unexpected_errors_hide_details_and_keep_a_request_id(
    app: Flask,
    client: FlaskClient,
    settings: Settings,
) -> None:
    @app.get("/api/_failure-probe")
    def failure_probe():
        raise RuntimeError(f"internal failure containing {settings.secret_key}")

    response = client.get("/api/_failure-probe")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
    }
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert settings.secret_key not in response.get_data(as_text=True)
    assert "Traceback" not in response.get_data(as_text=True)
