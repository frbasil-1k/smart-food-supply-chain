"""Pydantic request-validation helpers for blueprints.

Business services receive already-validated models. Route handlers never pass
raw request JSON into service code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from .errors import ApiError, pydantic_details


class StrictModel(BaseModel):
    """Reject unknown fields instead of silently dropping client input."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def parse_json[ModelT: BaseModel](model: type[ModelT], data: object) -> ModelT:
    """Validate ``data`` or raise a 422 ``validation_error``."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ApiError(
            422,
            "validation_error",
            "Request validation failed.",
            details=pydantic_details(exc),
        ) from exc
