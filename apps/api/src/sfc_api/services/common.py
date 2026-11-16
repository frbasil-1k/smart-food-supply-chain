"""Shared serialisation, pagination and atomic-error helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app
from pydantic import BaseModel, ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..errors import ApiError, pydantic_details


def decimal_str(value: Decimal | int | float | None, places: int = 2) -> str:
    if value is None:
        return f"{Decimal(0):.{places}f}"
    return f"{Decimal(value):.{places}f}"


def iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    zone = ZoneInfo(str(current_app.config.get("APP_TIMEZONE", "Asia/Kolkata")))
    value = value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)
    return value.isoformat(timespec="seconds")


def iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def page_params(args: Any, default_size: int = 25) -> tuple[int, int]:
    try:
        page = int(args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(args.get("page_size", default_size))
    except (TypeError, ValueError):
        page_size = default_size
    return max(1, page), min(100, max(1, page_size))


def pagination_meta(page: int, page_size: int, total: int) -> dict[str, Any]:
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def paginate(db: Session, stmt: Select[Any], page: int, page_size: int) -> tuple[list[Any], int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(db.scalar(count_stmt) or 0)
    rows = db.execute(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return list(rows), total


def apply_sort(
    stmt: Select[Any],
    sort: str | None,
    allowed: dict[str, Any],
    default: Sequence[Any],
) -> Select[Any]:
    if not sort:
        return stmt.order_by(*default)
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    column = allowed.get(key)
    if column is None:
        raise ApiError(
            422,
            "validation_error",
            "Unsupported sort field.",
            details=[{"field": "sort", "issue": "invalid"}],
        )
    return stmt.order_by(column.desc() if descending else column.asc())


def parse_model[T: BaseModel](model: type[T], payload: Any) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise ApiError(
            422,
            "validation_error",
            "Request validation failed.",
            details=pydantic_details(error),
        ) from error


def atomic(db: Session) -> None:
    """Commit one service transaction and translate MySQL/trigger errors."""
    try:
        db.commit()
    except ApiError:
        db.rollback()
        raise
    except (IntegrityError, DBAPIError) as error:
        db.rollback()
        raise map_db_error(error) from error
    except SQLAlchemyError as error:
        db.rollback()
        current_app.logger.exception("Database operation failed", extra={"event": "db_error"})
        raise ApiError(500, "internal_error", "An unexpected error occurred.") from error


def map_db_error(error: Exception) -> ApiError:
    orig = getattr(error, "orig", None)
    args: tuple[Any, ...] = tuple(getattr(orig, "args", ()) or ())
    code = args[0] if args else None
    message = str(args[1]) if len(args) > 1 else ""
    lowered = message.lower()
    if code == 1062 or "duplicate entry" in lowered:
        return ApiError(409, "duplicate_resource", "That record already exists.")
    if code == 1452 or "foreign key constraint fails" in lowered:
        return ApiError(422, "invalid_reference", "A referenced record does not exist.")
    if code == 3819 or "check constraint" in lowered:
        return ApiError(422, "validation_error", "The request violates a data constraint.")
    if code == 1644:
        if "role" in lowered:
            return ApiError(
                403, "role_not_permitted", "The database role rule rejected this action."
            )
        if "inspection has not passed" in lowered:
            return ApiError(409, "inspection_not_passed", "The latest inspection has not passed.")
        if "exceeds available" in lowered:
            return ApiError(
                409, "allocation_exceeds_available", "The quantity exceeds the available amount."
            )
        if "donation while" in lowered or "move a donation item" in lowered:
            return ApiError(
                409, "item_has_allocations", "This item is already referenced by logistics records."
            )
        if "below the quantity" in lowered:
            return ApiError(
                409,
                "below_allocated",
                "The quantity is below already allocated or spoiled amounts.",
            )
        if "driver" in lowered:
            return ApiError(409, "driver_required", "A valid attributed driver is required.")
        if "reviewer" in lowered or "review this delivery" in lowered:
            return ApiError(
                403, "forbidden", "Only the receiving branch manager can review this delivery."
            )
        if "append-only" in lowered:
            return ApiError(409, "append_only", "This record is append-only.")
        return ApiError(409, "constraint_violation", "The database rejected this change.")
    current_app.logger.warning(
        "Unmapped database error",
        extra={"event": "db_error_unmapped", "status": 500},
    )
    return ApiError(500, "internal_error", "An unexpected error occurred.")


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def as_list[T](value: Iterable[T] | None) -> list[T]:
    return list(value) if value else []
