"""Safety inspections and the inspector work queue."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, Response, current_app, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from ..auth.middleware import require_auth, require_roles
from ..config import Settings
from ..errors import ApiError
from ..models import Donation, InspectionLog
from ..responses import success
from ..schemas.requests import InspectionCreate
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.scope import donation_scope, get_inspection
from ..services.serializers import (
    donation_summary,
    inspection_payload,
)
from .helpers import actor, db, filter_value, int_filter, page, paged_response

bp = Blueprint("inspections", __name__, url_prefix="/api")


def _settings() -> Settings:
    return current_app.extensions["sfc_settings"]


@bp.get("/inspections")
@require_auth
def list_inspections() -> Response:
    db_session = db()
    user = actor()
    from ..services.scope import inspection_scope

    stmt = (
        select(InspectionLog)
        .options(
            joinedload(InspectionLog.donation),
            joinedload(InspectionLog.inspector),
        )
        .where(inspection_scope(user, db_session))
    )
    donation_id = int_filter("donation_id")
    if donation_id:
        stmt = stmt.where(InspectionLog.donation_id == donation_id)
    status = filter_value("status")
    if status:
        stmt = stmt.where(InspectionLog.safety_status == status)
    inspector_id = int_filter("inspector_id")
    if inspector_id:
        stmt = stmt.where(InspectionLog.inspector_user_id == inspector_id)
    date_from = filter_value("date_from")
    if date_from:
        try:
            stmt = stmt.where(InspectionLog.inspected_at >= datetime.fromisoformat(date_from))
        except ValueError as exc:
            raise ApiError(422, "validation_error", "date_from is not an ISO date.") from exc
    date_to = filter_value("date_to")
    if date_to:
        try:
            stmt = stmt.where(InspectionLog.inspected_at <= datetime.fromisoformat(date_to))
        except ValueError as exc:
            raise ApiError(422, "validation_error", "date_to is not an ISO date.") from exc
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {
            "inspected_at": InspectionLog.inspected_at,
            "inspection_id": InspectionLog.inspection_id,
            "status": InspectionLog.safety_status,
        },
        [InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db_session, stmt, page_number, page_size)
    return paged_response(
        [inspection_payload(row[0]) for row in rows], page_number, page_size, total
    )


@bp.get("/inspections/queue")
@require_roles("SAFETY_INSPECTOR", "NGO_MANAGER")
def inspection_queue() -> Response:
    db_session = db()
    user = actor()
    latest_id = (
        select(InspectionLog.inspection_id)
        .where(InspectionLog.donation_id == Donation.donation_id)
        .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
        .limit(1)
        .correlate(Donation)
        .scalar_subquery()
    )
    latest_status = (
        select(InspectionLog.safety_status)
        .where(InspectionLog.donation_id == Donation.donation_id)
        .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
        .limit(1)
        .correlate(Donation)
        .scalar_subquery()
    )
    stmt = (
        select(Donation)
        .options(
            joinedload(Donation.donor),
            joinedload(Donation.pickup_route),
            selectinload(Donation.items),
        )
        .where(
            Donation.donation_status == "COLLECTED",
            donation_scope(user, db_session),
            or_(latest_id.is_(None), func.coalesce(latest_status, "") != "PASSED"),
        )
        .order_by(Donation.pickup_datetime.asc(), Donation.donation_id.asc())
    )
    page_number, page_size = page()
    rows, total = paginate(db_session, stmt, page_number, page_size)
    payload = []
    for row in rows:
        donation = row[0]
        latest = db_session.execute(
            select(InspectionLog)
            .where(InspectionLog.donation_id == donation.donation_id)
            .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
            .limit(1)
        ).scalar_one_or_none()
        item = donation_summary(donation)
        item["latest_inspection"] = inspection_payload(latest) if latest else None
        payload.append(item)
    return paged_response(payload, page_number, page_size, total)


@bp.get("/inspections/<int:inspection_id>")
@require_auth
def get_inspection_detail(inspection_id: int) -> Response:
    row = get_inspection(db(), actor(), inspection_id)
    return success(inspection_payload(row))


@bp.post("/inspections")
@bp.post("/donations/<int:donation_id>/inspections")
@require_roles("SAFETY_INSPECTOR")
def create_inspection(donation_id: int | None = None) -> Response:
    payload = parse_model(InspectionCreate, request.get_json(silent=True))
    db_session = db()
    user = actor()
    body = request.get_json(silent=True) or {}
    if donation_id is None:
        donation_id = body.get("donation_id")
    if not isinstance(donation_id, int):
        raise ApiError(
            422,
            "validation_error",
            "donation_id is required.",
            details=[{"field": "donation_id", "issue": "missing"}],
        )
    donation = db_session.execute(
        select(Donation)
        .where(Donation.donation_id == donation_id, donation_scope(user, db_session))
        .with_for_update()
    ).scalar_one_or_none()
    if donation is None:
        raise ApiError(404, "not_found", "The requested donation was not found.")
    if donation.donation_status != "COLLECTED":
        raise ApiError(409, "invalid_transition", "Only collected donations can be inspected.")
    inspection = InspectionLog(
        donation_id=donation.donation_id,
        inspector_user_id=user.user_id,
        inspected_at=func.now(),
        temperature_c=payload.temperature_c,
        packaging_integrity=payload.packaging_integrity,
        safety_status=payload.safety_status,
        remarks=payload.remarks,
    )
    db_session.add(inspection)
    atomic(db_session)
    db_session.refresh(inspection)
    return success(inspection_payload(inspection), status=201)
