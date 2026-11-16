"""Spoilage intake with the database's quantity cap and derived reconciliation."""

from __future__ import annotations

from flask import Blueprint, Response, request
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from ..auth.middleware import require_auth, require_roles
from ..errors import ApiError
from ..models import Delivery, DeliveryItem, Donation, DonationItem, SpoilageRecord
from ..responses import success
from ..schemas.requests import SpoilageCreate
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.reconciliation import available_kg, recompute_donation
from ..services.scope import donation_scope, get_spoilage, spoilage_scope
from ..services.serializers import spoilage_payload
from .helpers import actor, db, int_filter, page, paged_response

bp = Blueprint("spoilage", __name__, url_prefix="/api/spoilage")


@bp.get("")
@require_auth
def list_spoilage() -> Response:
    db_session = db()
    user = actor()
    stmt = (
        select(SpoilageRecord)
        .options(
            joinedload(SpoilageRecord.food_item),
            joinedload(SpoilageRecord.reporter),
        )
        .where(spoilage_scope(user, db_session))
    )
    donation_id = int_filter("donation_id")
    if donation_id:
        stmt = stmt.where(
            SpoilageRecord.food_item_id.in_(
                select(DonationItem.food_item_id).where(DonationItem.donation_id == donation_id)
            )
        )
    item_id = int_filter("food_item_id")
    if item_id:
        stmt = stmt.where(SpoilageRecord.food_item_id == item_id)
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {"reported_at": SpoilageRecord.reported_at, "spoilage_id": SpoilageRecord.spoilage_id},
        [SpoilageRecord.reported_at.desc(), SpoilageRecord.spoilage_id.desc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db_session, stmt, page_number, page_size)
    return paged_response([spoilage_payload(row[0]) for row in rows], page_number, page_size, total)


@bp.get("/<int:spoilage_id>")
@require_auth
def get_spoilage_detail(spoilage_id: int) -> Response:
    return success(spoilage_payload(get_spoilage(db(), actor(), spoilage_id)))


@bp.post("")
@require_roles("NGO_MANAGER", "DRIVER")
def create_spoilage() -> Response:
    payload = parse_model(SpoilageCreate, request.get_json(silent=True))
    db_session = db()
    user = actor()
    item = db_session.execute(
        select(DonationItem)
        .where(DonationItem.food_item_id == payload.food_item_id)
        .with_for_update()
    ).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", "The requested food item was not found.")
    donation = db_session.get(Donation, item.donation_id)
    if donation is None:
        raise ApiError(404, "not_found", "The requested donation was not found.")
    if user.user_role == "NGO_MANAGER":
        in_scope = db_session.scalar(
            select(Donation.donation_id).where(
                Donation.donation_id == donation.donation_id,
                donation_scope(user, db_session),
            )
        )
        if in_scope is None:
            raise ApiError(404, "not_found", "The requested food item was not found.")
    else:
        delivered_to_driver = db_session.scalar(
            select(DeliveryItem.delivery_item_id)
            .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
            .where(
                DeliveryItem.food_item_id == item.food_item_id,
                Delivery.driver_user_id == user.user_id,
            )
            .limit(1)
        )
        if delivered_to_driver is None:
            raise ApiError(404, "not_found", "The requested food item was not found.")
    if donation.donation_status not in {"APPROVED", "PARTIALLY_DISTRIBUTED"}:
        raise ApiError(
            409, "invalid_transition", "Spoilage can only be recorded for approved food."
        )
    available = available_kg(db_session, item)
    if payload.quantity_spoiled_kg > available:
        raise ApiError(
            409,
            "allocation_exceeds_available",
            "The spoiled quantity exceeds the available donated quantity.",
            details=[{"field": "quantity_spoiled_kg", "issue": "allocation_exceeds_available"}],
        )
    record = SpoilageRecord(
        food_item_id=item.food_item_id,
        reported_by_user_id=user.user_id,
        quantity_kg=payload.quantity_spoiled_kg,
        reason=payload.reason,
        reported_at=func.now(),
    )
    db_session.add(record)
    db_session.flush()
    recompute_donation(db_session, donation.donation_id, user.user_id)
    atomic(db_session)
    db_session.refresh(record)
    return success(spoilage_payload(record), status=201)
