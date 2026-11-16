"""Delivery allocation, driver workflow, reviews and driver assignments."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..auth.middleware import require_auth, require_roles
from ..config import Settings
from ..errors import ApiError
from ..models import (
    AppUser,
    Delivery,
    DeliveryItem,
    DeliveryReview,
    Donation,
    DonationItem,
    InspectionLog,
    Route,
)
from ..responses import success
from ..schemas.requests import (
    DeliveryCreate,
    DeliveryItemCreate,
    DeliveryItemPatch,
    DeliveryPatch,
    DeliveryStatusPatch,
    ReviewCreate,
)
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.reconciliation import available_kg, recompute_donation, remove_delivery_items
from ..services.scope import (
    delivery_scope,
    get_delivery,
    get_donation,
    managed_branch_ids,
)
from ..services.serializers import delivery_payload
from .helpers import actor, db, filter_value, int_filter, page, paged_response

bp = Blueprint("deliveries", __name__, url_prefix="/api")


def _settings() -> Settings:
    return current_app.extensions["sfc_settings"]


def _loaded(db_session: Session, delivery_id: int) -> Delivery:
    return db_session.execute(
        select(Delivery)
        .options(
            joinedload(Delivery.donation).joinedload(Donation.donor),
            joinedload(Delivery.route),
            joinedload(Delivery.driver),
            joinedload(Delivery.recipient_branch),
            selectinload(Delivery.items).joinedload(DeliveryItem.food_item),
            joinedload(Delivery.review).joinedload(DeliveryReview.reviewer),
        )
        .where(Delivery.delivery_id == delivery_id)
    ).scalar_one()


def _read_delivery(delivery_id: int) -> Delivery:
    delivery = get_delivery(db(), actor(), delivery_id)
    return _loaded(db(), delivery.delivery_id)


@bp.get("/deliveries")
@require_roles("DONOR", "NGO_MANAGER", "DRIVER")
def list_deliveries() -> Response:
    db_session = db()
    user = actor()
    stmt = select(Delivery).where(delivery_scope(user, db_session))
    status = filter_value("status")
    if status:
        stmt = stmt.where(Delivery.delivery_status == status)
    donation_id = int_filter("donation_id")
    if donation_id:
        stmt = stmt.where(Delivery.donation_id == donation_id)
    route_id = int_filter("route_id")
    if route_id:
        stmt = stmt.where(Delivery.route_id == route_id)
    branch_id = int_filter("branch_id")
    if branch_id:
        stmt = stmt.where(Delivery.recipient_branch_id == branch_id)
    driver_id = int_filter("driver_user_id") or int_filter("driver_id")
    if driver_id:
        stmt = stmt.where(Delivery.driver_user_id == driver_id)
    date_from = filter_value("from")
    if date_from:
        stmt = stmt.where(Delivery.scheduled_for >= datetime.fromisoformat(date_from))
    date_to = filter_value("to")
    if date_to:
        stmt = stmt.where(Delivery.scheduled_for <= datetime.fromisoformat(date_to))
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {
            "delivery_id": Delivery.delivery_id,
            "scheduled_for": Delivery.scheduled_for,
            "status": Delivery.delivery_status,
            "delivered_at": Delivery.delivered_at,
        },
        [Delivery.delivery_id.desc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db_session, stmt, page_number, page_size)
    ids = [row[0].delivery_id for row in rows]
    if not ids:
        return paged_response([], page_number, page_size, total)
    loaded = (
        db_session.execute(
            select(Delivery)
            .options(
                joinedload(Delivery.donation).joinedload(Donation.donor),
                joinedload(Delivery.route),
                joinedload(Delivery.driver),
                joinedload(Delivery.recipient_branch),
            )
            .where(Delivery.delivery_id.in_(ids))
            .order_by(Delivery.delivery_id.desc())
        )
        .scalars()
        .all()
    )
    return paged_response([delivery_payload(row) for row in loaded], page_number, page_size, total)


@bp.post("/deliveries")
@require_roles("NGO_MANAGER")
def create_delivery() -> Response:
    payload = parse_model(DeliveryCreate, request.get_json(silent=True))
    db_session = db()
    user = actor()
    donation = get_donation(db_session, user, payload.donation_id)
    if donation.donation_status not in {"APPROVED", "PARTIALLY_DISTRIBUTED"}:
        raise ApiError(409, "invalid_transition", "Only approved donations can be allocated.")
    route = db_session.get(Route, payload.route_id)
    if route is None or route.managing_branch_id not in managed_branch_ids(
        db_session, user.user_id
    ):
        raise ApiError(404, "not_found", "The requested route was not found.")
    if route.route_status != "ACTIVE":
        raise ApiError(409, "inactive_route", "The route is not active.")
    if payload.recipient_branch_id not in managed_branch_ids(db_session, user.user_id):
        raise ApiError(404, "not_found", "The receiving branch was not found.")
    driver_id = payload.driver_user_id or route.designated_driver_user_id
    driver = db_session.get(AppUser, driver_id)
    if driver is None or driver.user_role != "DRIVER" or driver.account_status != "ACTIVE":
        raise ApiError(422, "driver_not_eligible", "The driver is not active.")
    if (
        payload.driver_user_id is not None
        and payload.driver_user_id != route.designated_driver_user_id
    ):
        from ..models import RouteAssignment

        assigned = db_session.scalar(
            select(RouteAssignment.user_id).where(
                RouteAssignment.route_id == route.route_id,
                RouteAssignment.user_id == payload.driver_user_id,
            )
        )
        if assigned is None:
            raise ApiError(422, "driver_not_eligible", "The driver is not eligible for this route.")
    seen: set[int] = set()
    for line in payload.items:
        if line.food_item_id in seen:
            raise ApiError(
                422, "validation_error", "A food item may appear only once per delivery."
            )
        seen.add(line.food_item_id)
    item_ids = sorted(seen)
    items = (
        db_session.execute(
            select(DonationItem)
            .where(
                DonationItem.donation_id == donation.donation_id,
                DonationItem.food_item_id.in_(item_ids),
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    items_by_id = {item.food_item_id: item for item in items}
    if set(items_by_id) != seen:
        raise ApiError(422, "invalid_reference", "A food item does not belong to this donation.")
    for line in payload.items:
        available = available_kg(db_session, items_by_id[line.food_item_id])
        if line.quantity_delivered_kg > available:
            raise ApiError(
                409,
                "allocation_exceeds_available",
                "The requested quantity exceeds the available donated quantity.",
                details=[{"field": "items", "issue": "allocation_exceeds_available"}],
            )
    delivery = Delivery(
        donation_id=donation.donation_id,
        route_id=route.route_id,
        driver_user_id=driver_id,
        recipient_branch_id=payload.recipient_branch_id,
        scheduled_for=payload.scheduled_for,
        delivery_status="PLANNED",
    )
    db_session.add(delivery)
    db_session.flush()
    for line in payload.items:
        db_session.add(
            DeliveryItem(
                delivery_id=delivery.delivery_id,
                food_item_id=line.food_item_id,
                allocated_quantity_kg=line.quantity_delivered_kg,
            )
        )
    atomic(db_session)
    return success(
        delivery_payload(_loaded(db_session, delivery.delivery_id), detail=True), status=201
    )


@bp.get("/deliveries/<int:delivery_id>")
@require_roles("DONOR", "NGO_MANAGER", "DRIVER")
def delivery_detail(delivery_id: int) -> Response:
    return success(delivery_payload(_read_delivery(delivery_id), detail=True))


@bp.patch("/deliveries/<int:delivery_id>")
@require_roles("NGO_MANAGER")
def patch_delivery(delivery_id: int) -> Response:
    db_session = db()
    delivery = get_delivery(db_session, actor(), delivery_id)
    if delivery.delivery_status != "PLANNED":
        raise ApiError(409, "invalid_transition", "Only a planned delivery can be edited.")
    payload = parse_model(DeliveryPatch, request.get_json(silent=True))
    if "driver_user_id" in payload.model_fields_set:
        if payload.driver_user_id is None:
            delivery.driver_user_id = None
        else:
            driver = db_session.get(AppUser, payload.driver_user_id)
            if driver is None or driver.user_role != "DRIVER" or driver.account_status != "ACTIVE":
                raise ApiError(422, "invalid_reference", "The driver is not active.")
            delivery.driver_user_id = payload.driver_user_id
    if "scheduled_for" in payload.model_fields_set:
        delivery.scheduled_for = payload.scheduled_for
    atomic(db_session)
    return success(delivery_payload(_loaded(db_session, delivery.delivery_id), detail=True))


@bp.patch("/deliveries/<int:delivery_id>/status")
@require_roles("NGO_MANAGER", "DRIVER")
def change_delivery_status(delivery_id: int) -> Response:
    db_session = db()
    user = actor()
    payload = parse_model(DeliveryStatusPatch, request.get_json(silent=True))
    delivery = db_session.execute(
        select(Delivery)
        .where(Delivery.delivery_id == delivery_id, delivery_scope(user, db_session))
        .with_for_update()
    ).scalar_one_or_none()
    if delivery is None:
        raise ApiError(404, "not_found", "The requested delivery was not found.")
    current = delivery.delivery_status
    target = payload.target_status
    if current == "FAILED":
        raise ApiError(409, "invalid_transition", "A failed delivery is terminal in Step 7.")
    if user.user_role == "NGO_MANAGER":
        allowed = (current == "PLANNED" and target in {"CANCELLED", "FAILED"}) or (
            current == "IN_TRANSIT" and target == "FAILED"
        )
    else:
        if delivery.driver_user_id != user.user_id:
            raise ApiError(404, "not_found", "The requested delivery was not found.")
        allowed = (current == "PLANNED" and target == "IN_TRANSIT") or (
            current == "IN_TRANSIT" and target in {"DELIVERED", "FAILED"}
        )
    if not allowed:
        raise ApiError(409, "invalid_transition", "That delivery transition is not permitted.")
    if target == "IN_TRANSIT" and delivery.driver_user_id is None:
        raise ApiError(409, "driver_required", "A driver must be assigned before departure.")
    if (
        target == "IN_TRANSIT"
        and delivery.driver_user_id != user.user_id
        and user.user_role == "DRIVER"
    ):
        raise ApiError(403, "forbidden", "Only the attributed driver can depart.")
    if target == "CANCELLED":
        remove_delivery_items(db_session, delivery.delivery_id)
        db_session.flush()
    if target == "DELIVERED":
        latest = db_session.execute(
            select(InspectionLog)
            .where(InspectionLog.donation_id == delivery.donation_id)
            .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest is None or latest.safety_status != "PASSED":
            raise ApiError(409, "inspection_not_passed", "The latest inspection has not passed.")
    delivery.delivery_status = target
    if target == "DELIVERED":
        delivery.delivered_at = func.now()
    db_session.flush()
    if target == "DELIVERED":
        recompute_donation(db_session, delivery.donation_id, user.user_id)
    atomic(db_session)
    return success(delivery_payload(_loaded(db_session, delivery.delivery_id), detail=True))


@bp.post("/deliveries/<int:delivery_id>/items")
@require_roles("NGO_MANAGER")
def add_delivery_item(delivery_id: int) -> Response:
    db_session = db()
    delivery = get_delivery(db_session, actor(), delivery_id)
    if delivery.delivery_status != "PLANNED":
        raise ApiError(409, "invalid_transition", "Items can only be added to a planned delivery.")
    payload = parse_model(DeliveryItemCreate, request.get_json(silent=True))
    item = db_session.execute(
        select(DonationItem)
        .where(
            DonationItem.food_item_id == payload.food_item_id,
            DonationItem.donation_id == delivery.donation_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if item is None:
        raise ApiError(422, "invalid_reference", "The food item does not belong to this donation.")
    if payload.quantity_delivered_kg > available_kg(db_session, item):
        raise ApiError(409, "allocation_exceeds_available", "The quantity exceeds available stock.")
    db_session.add(
        DeliveryItem(
            delivery_id=delivery.delivery_id,
            food_item_id=item.food_item_id,
            allocated_quantity_kg=payload.quantity_delivered_kg,
        )
    )
    atomic(db_session)
    return success(
        delivery_payload(_loaded(db_session, delivery.delivery_id), detail=True), status=201
    )


@bp.patch("/deliveries/<int:delivery_id>/items/<int:delivery_item_id>")
@require_roles("NGO_MANAGER")
def patch_delivery_item(delivery_id: int, delivery_item_id: int) -> Response:
    db_session = db()
    delivery = get_delivery(db_session, actor(), delivery_id)
    if delivery.delivery_status != "PLANNED":
        raise ApiError(409, "invalid_transition", "Items can only be edited on a planned delivery.")
    line = db_session.get(DeliveryItem, delivery_item_id)
    if line is None or line.delivery_id != delivery.delivery_id:
        raise ApiError(404, "not_found", "The requested delivery item was not found.")
    payload = parse_model(DeliveryItemPatch, request.get_json(silent=True))
    item = db_session.execute(
        select(DonationItem).where(DonationItem.food_item_id == line.food_item_id).with_for_update()
    ).scalar_one()
    other_allocated = Decimal(
        db_session.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0)).where(
                DeliveryItem.food_item_id == line.food_item_id,
                DeliveryItem.delivery_item_id != line.delivery_item_id,
            )
        )
        or 0
    )
    from ..models import SpoilageRecord

    spoiled = Decimal(
        db_session.scalar(
            select(func.coalesce(func.sum(SpoilageRecord.quantity_kg), 0)).where(
                SpoilageRecord.food_item_id == line.food_item_id
            )
        )
        or 0
    )
    if payload.quantity_delivered_kg > Decimal(item.quantity_kg) - other_allocated - spoiled:
        raise ApiError(409, "allocation_exceeds_available", "The quantity exceeds available stock.")
    line.allocated_quantity_kg = payload.quantity_delivered_kg
    atomic(db_session)
    return success(delivery_payload(_loaded(db_session, delivery.delivery_id), detail=True))


@bp.delete("/deliveries/<int:delivery_id>/items/<int:delivery_item_id>")
@require_roles("NGO_MANAGER")
def delete_delivery_item(delivery_id: int, delivery_item_id: int) -> Response:
    db_session = db()
    delivery = get_delivery(db_session, actor(), delivery_id)
    if delivery.delivery_status != "PLANNED":
        raise ApiError(
            409, "invalid_transition", "Items can only be removed from a planned delivery."
        )
    line = db_session.get(DeliveryItem, delivery_item_id)
    if line is None or line.delivery_id != delivery.delivery_id:
        raise ApiError(404, "not_found", "The requested delivery item was not found.")
    db_session.delete(line)
    atomic(db_session)
    return Response(status=204)


@bp.get("/deliveries/<int:delivery_id>/review")
@require_auth
def get_review(delivery_id: int) -> Response:
    delivery = _read_delivery(delivery_id)
    if delivery.review is None:
        raise ApiError(404, "not_found", "This delivery has not been reviewed.")
    return success(delivery_payload(delivery, detail=True)["review"])


@bp.post("/deliveries/<int:delivery_id>/review")
@require_roles("NGO_MANAGER")
def create_review(delivery_id: int) -> Response:
    db_session = db()
    delivery = get_delivery(db_session, actor(), delivery_id)
    if delivery.delivery_status != "DELIVERED":
        raise ApiError(409, "invalid_transition", "Only a delivered delivery can be reviewed.")
    recipient = delivery.recipient_branch
    if recipient is None or recipient.regional_manager_user_id != actor().user_id:
        raise ApiError(
            403, "forbidden", "Only the receiving branch manager can review this delivery."
        )
    payload = parse_model(ReviewCreate, request.get_json(silent=True))
    if (
        db_session.scalar(
            select(DeliveryReview.review_id).where(
                DeliveryReview.delivery_id == delivery.delivery_id
            )
        )
        is not None
    ):
        raise ApiError(409, "duplicate_review", "This delivery has already been reviewed.")
    review = DeliveryReview(
        delivery_id=delivery.delivery_id,
        reviewed_by_user_id=actor().user_id,
        rating=payload.rating,
        comment=payload.quality_notes,
        review_date=func.now(),
    )
    db_session.add(review)
    atomic(db_session)
    db_session.refresh(review)
    return success(
        {
            "review_id": review.review_id,
            "delivery_id": review.delivery_id,
            "rating": review.rating,
            "quality_notes": review.comment,
            "review_date": (
                review.review_date.isoformat(timespec="seconds")
                if review.review_date is not None
                else None
            ),
        },
        status=201,
    )


@bp.get("/driver/assignments")
@require_roles("DRIVER")
def driver_assignments() -> Response:
    db_session = db()
    user = actor()
    scope = filter_value("scope") or "today"
    stmt = (
        select(Delivery)
        .options(
            joinedload(Delivery.donation).joinedload(Donation.donor),
            joinedload(Delivery.route),
            joinedload(Delivery.recipient_branch),
            selectinload(Delivery.items).joinedload(DeliveryItem.food_item),
        )
        .where(
            Delivery.driver_user_id == user.user_id,
            Delivery.delivery_status.in_(("PLANNED", "IN_TRANSIT")),
        )
    )
    today = datetime.now(ZoneInfo(_settings().timezone)).date()
    if scope == "today":
        stmt = stmt.where(func.date(Delivery.scheduled_for) == today)
    elif scope == "upcoming":
        stmt = stmt.where(func.date(Delivery.scheduled_for) >= today)
    stmt = stmt.order_by(Delivery.scheduled_for.asc(), Delivery.delivery_id.asc())
    rows = db_session.execute(stmt).scalars().all()
    return success([delivery_payload(row) for row in rows])


@bp.patch("/delivery-items/<int:delivery_item_id>")
@require_roles("NGO_MANAGER")
def patch_delivery_item_flat(delivery_item_id: int) -> Response:
    line = db().get(DeliveryItem, delivery_item_id)
    if line is None:
        raise ApiError(404, "not_found", "The requested delivery item was not found.")
    get_delivery(db(), actor(), line.delivery_id)
    return patch_delivery_item(line.delivery_id, delivery_item_id)


@bp.delete("/delivery-items/<int:delivery_item_id>")
@require_roles("NGO_MANAGER")
def delete_delivery_item_flat(delivery_item_id: int) -> Response:
    line = db().get(DeliveryItem, delivery_item_id)
    if line is None:
        raise ApiError(404, "not_found", "The requested delivery item was not found.")
    get_delivery(db(), actor(), line.delivery_id)
    return delete_delivery_item(line.delivery_id, delivery_item_id)
