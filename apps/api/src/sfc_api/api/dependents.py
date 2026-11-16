"""Driver-owned dependents, including composite-key allocation."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, request
from sqlalchemy import func, select

from ..auth.middleware import require_roles
from ..errors import ApiError
from ..models import Dependent
from ..responses import success
from ..schemas.requests import DependentCreate, DependentPatch
from ..services.common import atomic, parse_model
from .helpers import actor, db

bp = Blueprint("dependents", __name__, url_prefix="/api/dependents")


def _payload(row: Dependent) -> dict[str, Any]:
    return {
        "dependent_no": row.dependent_no,
        "full_name": row.full_name,
        "relationship": row.relationship_name,
        "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
        "phone": row.phone,
    }


@bp.get("")
@require_roles("DRIVER")
def list_dependents() -> Response:
    rows = (
        db()
        .execute(
            select(Dependent)
            .where(Dependent.driver_user_id == actor().user_id)
            .order_by(Dependent.dependent_no.asc())
        )
        .scalars()
        .all()
    )
    return success([_payload(row) for row in rows])


@bp.post("")
@require_roles("DRIVER")
def create_dependent() -> Response:
    payload = parse_model(DependentCreate, request.get_json(silent=True))
    db_session = db()
    next_no = (
        db_session.scalar(
            select(func.coalesce(func.max(Dependent.dependent_no), 0)).where(
                Dependent.driver_user_id == actor().user_id
            )
        )
        or 0
    ) + 1
    row = Dependent(
        driver_user_id=actor().user_id,
        dependent_no=next_no,
        full_name=payload.full_name,
        relationship_name=payload.relationship,
        date_of_birth=payload.date_of_birth,
        phone=payload.phone,
    )
    db_session.add(row)
    atomic(db_session)
    return success(_payload(row), status=201)


@bp.patch("/<int:driver_user_id>/<int:dependent_no>")
@bp.patch("/<int:dependent_no>")
@require_roles("DRIVER")
def patch_dependent(dependent_no: int, driver_user_id: int | None = None) -> Response:
    if driver_user_id is not None and driver_user_id != actor().user_id:
        raise ApiError(404, "not_found", "The requested dependent was not found.")
    db_session = db()
    row = db_session.get(Dependent, (actor().user_id, dependent_no))
    if row is None:
        raise ApiError(404, "not_found", "The requested dependent was not found.")
    payload = parse_model(DependentPatch, request.get_json(silent=True))
    if "full_name" in payload.model_fields_set and payload.full_name is not None:
        row.full_name = payload.full_name
    if "relationship" in payload.model_fields_set and payload.relationship is not None:
        row.relationship_name = payload.relationship
    if "date_of_birth" in payload.model_fields_set:
        row.date_of_birth = payload.date_of_birth
    if "phone" in payload.model_fields_set:
        row.phone = payload.phone
    atomic(db_session)
    return success(_payload(row))


@bp.delete("/<int:driver_user_id>/<int:dependent_no>")
@bp.delete("/<int:dependent_no>")
@require_roles("DRIVER")
def delete_dependent(dependent_no: int, driver_user_id: int | None = None) -> Response:
    if driver_user_id is not None and driver_user_id != actor().user_id:
        raise ApiError(404, "not_found", "The requested dependent was not found.")
    db_session = db()
    row = db_session.get(Dependent, (actor().user_id, dependent_no))
    if row is None:
        raise ApiError(404, "not_found", "The requested dependent was not found.")
    db_session.delete(row)
    atomic(db_session)
    return Response(status=204)
