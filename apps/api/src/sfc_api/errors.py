"""Uniform error envelopes and safe exception handling."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from flask import Flask, Response, g, jsonify, request
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from .responses import JSON_CONTENT_TYPE

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An expected, client-facing application error."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def pydantic_details(error: ValidationError) -> list[dict[str, str]]:
    """Reduce Pydantic errors to the contract's stable detail fields."""
    details: list[dict[str, str]] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "__root__"
        details.append({"field": location, "issue": item["type"]})
    return details


def _request_id() -> str:
    return getattr(g, "request_id", None) or uuid4().hex


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, str]] | None = None,
) -> Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details

    request_id = _request_id()
    response = jsonify({"error": error, "request_id": request_id})
    response.status_code = status_code
    response.content_type = JSON_CONTENT_TYPE
    response.headers["X-Request-ID"] = request_id
    return response


def _http_error_response(error: HTTPException) -> Response:
    status_code = error.code or 500
    if status_code == 404:
        code = "not_found"
        message = "The requested resource was not found."
    elif status_code == 401:
        code = "unauthenticated"
        message = "Authentication is required."
    elif status_code == 403:
        code = "forbidden"
        message = "The request is not permitted."
    elif status_code == 429:
        code = "rate_limited"
        message = "Too many requests."
    elif status_code < 500:
        code = "malformed_request"
        message = "The request could not be processed."
    else:
        code = "internal_error"
        message = "An unexpected error occurred."
    return error_response(status_code, code, message)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> Response:
        return error_response(
            error.status_code,
            error.code,
            error.message,
            details=error.details,
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError) -> Response:
        return error_response(
            422,
            "validation_error",
            "Request validation failed.",
            details=pydantic_details(error),
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> Response:
        return _http_error_response(error)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Response:
        # The server log keeps the traceback; the client never sees it.
        app.logger.exception(
            "Unhandled application error on %s %s",
            request.method,
            request.path,
            extra={"event": "unhandled_exception"},
        )
        return error_response(
            500,
            "internal_error",
            "An unexpected error occurred.",
        )
