"""Small HTTP-layer helpers shared by feature blueprints."""

from __future__ import annotations

from typing import Any

from flask import g, request
from sqlalchemy.orm import Session

from ..auth.middleware import current_user
from ..extensions import get_session
from ..models import AppUser
from ..responses import success
from ..services.common import page_params, pagination_meta


def actor() -> AppUser:
    return current_user()


def db() -> Session:
    return get_session()


def page() -> tuple[int, int]:
    return page_params(request.args)


def paged_response(
    data: list[dict[str, Any]],
    page_number: int,
    page_size: int,
    total: int,
) -> Any:
    return success(
        data,
        meta={"pagination": pagination_meta(page_number, page_size, total)},
    )


def filter_value(name: str) -> str | None:
    value = request.args.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def int_filter(name: str) -> int | None:
    value = filter_value(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        from ..errors import ApiError

        raise ApiError(422, "validation_error", f"{name} must be an integer.") from None


def bool_filter(name: str) -> bool | None:
    value = filter_value(name)
    if value is None:
        return None
    return value.lower() in {"1", "true", "yes", "on"}


def request_id() -> str | None:
    return g.get("request_id")
