"""Response envelopes shared by every API route."""

from __future__ import annotations

from typing import Any

from flask import Response, jsonify

JSON_CONTENT_TYPE = "application/json; charset=utf-8"


def success(
    data: Any,
    *,
    meta: dict[str, Any] | None = None,
    status: int = 200,
) -> Response:
    """Return the contract's success envelope with an explicit UTF-8 type."""
    response = jsonify({"data": data, "meta": meta if meta is not None else {}})
    response.status_code = status
    response.content_type = JSON_CONTENT_TYPE
    return response
