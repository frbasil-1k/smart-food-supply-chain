"""Donation registration, routing, lifecycle and item endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..auth.middleware import require_auth, require_roles
from ..config import Settings
from ..errors import ApiError
from ..models import (
    AppUser,
    Delivery,
    Donation,
    DonationItem,
    DonationStatusHistory,
    FoodCategory,
    InspectionLog,
    Route,
)
from ..responses import success
from ..schemas.requests import (
    DonationCreate,
    DonationItemCreate,
    DonationItemPatch,
    DonationPatch,
    DonationRoutePatch,
    DonationStatusPatch,
)
from ..services.common import apply_sort, atomic, iso_datetime, paginate, parse_model
from ..services.scope import donation_scope, get_donation, get_item, managed_branch_ids
from ..services.serializers import (
    donation_detail,
    donation_summary,
    history_payload,
    item_payload,
)
from .helpers import actor, db, filter_value, int_filter, page, paged_response

bp = Blueprint("donations", __name__, url_prefix="/api/donations")


def _settings() -> Settings:
    return current_app.extensions["sfc_settings"]


def _now() -> datetime:
    return datetime.now(ZoneInfo(_settings().timezone)).replace(tzinfo=None)


def _loaded(db_session: Session, donation_id: int) -> Donation:
    return db_session.execute(
        select(Donation)
        .options(
            joinedload(Donation.donor),
            joinedload(Donation.pickup_route).joinedload(Route.designated_driver),
            selectinload(Donation.items).joinedload(DonationItem.category),
            selectinload(Donation.deliveries).joinedload(Delivery.recipient_branch),
            selectinload(Donation.deliveries).joinedload(Delivery.driver),
            selectinload(Donation.deliveries).joinedload(Delivery.route),
            selectinload(Donation.history).joinedload(DonationStatusHistory.changed_by),
        )
        .where(Donation.donation_id == donation_id)
    ).scalar_one()


def _validate_route(db_session: Session, user: AppUser, route_id: int | None) -> Route | None:
    if route_id is None:
        return None
    route = db_session.get(Route, route_id)
    if route is None:
        raise ApiError(422, "invalid_reference", "The pickup route does not exist.")
    if user.primary_branch_id is None:
        raise ApiError(
            422,
            "donor_branch_required",
            "A donor must have a primary branch before selecting a route.",
        )
    if route.route_status != "ACTIVE" or route.route_type not in {"PICKUP", "MIXED"}:
        raise ApiError(422, "invalid_reference", "The pickup route is not usable.")
    if user.primary_branch_id != route.managing_branch_id:
        raise ApiError(422, "invalid_reference", "The pickup route is outside your branch.")
    return route


def _validate_items(db_session: Session, items: list[DonationItemCreate]) -> None:
    category_ids = {item.category_id for item in items}
    existing = set(
        db_session.scalars(
            select(FoodCategory.category_id).where(FoodCategory.category_id.in_(category_ids))
        ).all()
    )
    if existing != category_ids:
        raise ApiError(422, "invalid_reference", "A food category does not exist.")
    for item in items:
        if item.prepared_at is not None and item.best_before <= item.prepared_at:
            raise ApiError(422, "validation_error", "best_before must be after prepared_at.")


@bp.get("")
@require_auth
def list_donations() -> Response:
    db_session = db()
    user = actor()
    stmt = select(Donation).where(donation_scope(user, db_session))
    status = filter_value("status")
    if status:
        stmt = stmt.where(Donation.donation_status == status)
    urgency = filter_value("urgency")
    if urgency:
        stmt = stmt.where(Donation.urgency_level == urgency)
    donor_id = int_filter("donor_id")
    if donor_id:
        stmt = stmt.where(Donation.donor_user_id == donor_id)
    route_id = int_filter("route_id")
    if route_id:
        stmt = stmt.where(Donation.pickup_route_id == route_id)
    branch_id = int_filter("branch_id")
    if branch_id:
        stmt = stmt.where(
            or_(
                Donation.pickup_route_id.in_(
                    select(Route.route_id).where(Route.managing_branch_id == branch_id)
                ),
                Donation.donor_user_id.in_(
                    select(AppUser.user_id).where(AppUser.primary_branch_id == branch_id)
                ),
            )
        )
    q = filter_value("q")
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Donation.pickup_address.like(pattern),
                Donation.donation_id.in_(
                    select(DonationItem.donation_id).where(DonationItem.item_name.like(pattern))
                ),
            )
        )
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {
            "pickup_datetime": Donation.pickup_datetime,
            "status": Donation.donation_status,
            "donation_id": Donation.donation_id,
            "urgency": Donation.urgency_level,
        },
        [Donation.pickup_datetime.desc(), Donation.donation_id.desc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db_session, stmt, page_number, page_size)
    ids = [row[0].donation_id for row in rows]
    if not ids:
        return paged_response([], page_number, page_size, total)
    loaded = (
        db_session.execute(
            select(Donation)
            .options(
                joinedload(Donation.donor),
                joinedload(Donation.pickup_route),
                selectinload(Donation.items),
            )
            .where(Donation.donation_id.in_(ids))
            .order_by(Donation.pickup_datetime.desc(), Donation.donation_id.desc())
        )
        .scalars()
        .all()
    )
    return paged_response([donation_summary(row) for row in loaded], page_number, page_size, total)


@bp.post("")
@require_roles("DONOR")
def create_donation() -> Response:
    payload = parse_model(DonationCreate, request.get_json(silent=True))
    db_session = db()
    user = actor()
    if payload.pickup_datetime < _now() - timedelta(minutes=5):
        raise ApiError(422, "validation_error", "Pickup time cannot be in the past.")
    _validate_route(db_session, user, payload.pickup_route_id)
    _validate_items(db_session, payload.items)
    donation = Donation(
        donor_user_id=user.user_id,
        pickup_route_id=payload.pickup_route_id,
        pickup_datetime=payload.pickup_datetime,
        pickup_address=payload.pickup_address,
        pickup_pincode=payload.pickup_pincode,
        pickup_contact=payload.pickup_contact,
        donation_status="PENDING",
        urgency_level=payload.urgency_level,
    )
    db_session.add(donation)
    db_session.flush()
    for item in payload.items:
        db_session.add(
            DonationItem(
                donation_id=donation.donation_id,
                category_id=item.category_id,
                item_name=item.item_name,
                quantity_kg=item.quantity_kg,
                prepared_at=item.prepared_at,
                best_before=item.best_before,
            )
        )
    db_session.add(
        DonationStatusHistory(
            donation_id=donation.donation_id,
            from_status=None,
            to_status="PENDING",
            changed_by_user_id=user.user_id,
            changed_at=func.now(),
            is_reconstructed=False,
            note="Donation registered",
        )
    )
    atomic(db_session)
    return success(
        donation_detail(db_session, _loaded(db_session, donation.donation_id)), status=201
    )


@bp.get("/<int:donation_id>")
@require_auth
def get_donation_detail(donation_id: int) -> Response:
    donation = get_donation(db(), actor(), donation_id)
    return success(donation_detail(db(), _loaded(db(), donation.donation_id)))


@bp.patch("/<int:donation_id>")
@require_roles("DONOR")
def patch_donation(donation_id: int) -> Response:
    db_session = db()
    donation = get_donation(db_session, actor(), donation_id)
    if donation.donor_user_id != actor().user_id:
        raise ApiError(404, "not_found", "The requested donation was not found.")
    if donation.donation_status not in {"PENDING", "SCHEDULED"}:
        raise ApiError(409, "invalid_transition", "This donation can no longer be edited.")
    payload = parse_model(DonationPatch, request.get_json(silent=True))
    if payload.pickup_datetime is not None:
        donation.pickup_datetime = payload.pickup_datetime
    for field in ("pickup_address", "pickup_pincode", "pickup_contact", "urgency_level"):
        if field in payload.model_fields_set:
            setattr(donation, field, getattr(payload, field))
    atomic(db_session)
    return success(donation_detail(db_session, _loaded(db_session, donation.donation_id)))


@bp.patch("/<int:donation_id>/route")
@require_roles("NGO_MANAGER")
def assign_route(donation_id: int) -> Response:
    db_session = db()
    donation = get_donation(db_session, actor(), donation_id)
    if donation.donation_status not in {"PENDING", "SCHEDULED"}:
        raise ApiError(409, "invalid_transition", "The route cannot be changed at this stage.")
    payload = parse_model(DonationRoutePatch, request.get_json(silent=True))
    route = db_session.get(Route, payload.pickup_route_id)
    if route is None or route.managing_branch_id not in managed_branch_ids(
        db_session, actor().user_id
    ):
        raise ApiError(404, "not_found", "The requested route was not found.")
    if route.route_status != "ACTIVE":
        raise ApiError(409, "inactive_route", "The route is not active.")
    donation.pickup_route_id = route.route_id
    atomic(db_session)
    return success(donation_detail(db_session, _loaded(db_session, donation.donation_id)))


def _append_history(
    db_session: Session,
    donation: Donation,
    actor_id: int,
    target: str,
    note: str | None,
) -> DonationStatusHistory:
    row = DonationStatusHistory(
        donation_id=donation.donation_id,
        from_status=donation.donation_status,
        to_status=target,
        changed_by_user_id=actor_id,
        changed_at=func.now(),
        is_reconstructed=False,
        note=note,
    )
    db_session.add(row)
    return row


@bp.patch("/<int:donation_id>/status")
@require_auth
def change_status(donation_id: int) -> Response:
    db_session = db()
    user = actor()
    payload = parse_model(DonationStatusPatch, request.get_json(silent=True))
    donation = db_session.execute(
        select(Donation)
        .where(Donation.donation_id == donation_id, donation_scope(user, db_session))
        .with_for_update()
    ).scalar_one_or_none()
    if donation is None:
        raise ApiError(404, "not_found", "The requested donation was not found.")
    current = donation.donation_status
    target = payload.target_status
    if target in {"PARTIALLY_DISTRIBUTED", "COMPLETED"}:
        raise ApiError(422, "validation_error", "System-derived statuses cannot be set directly.")
    route = donation.pickup_route
    latest = db_session.execute(
        select(InspectionLog)
        .where(InspectionLog.donation_id == donation.donation_id)
        .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if user.user_role == "DONOR":
        if donation.donor_user_id != user.user_id or current != "PENDING" or target != "CANCELLED":
            raise ApiError(409, "invalid_transition", "That status change is not permitted.")
        if (
            db_session.scalar(
                select(Delivery.delivery_id).where(Delivery.donation_id == donation.donation_id)
            )
            is not None
        ):
            raise ApiError(
                409, "invalid_transition", "A donation with a delivery cannot be cancelled."
            )
    elif user.user_role == "NGO_MANAGER":
        allowed: dict[tuple[str | None, str], bool] = {
            ("PENDING", "SCHEDULED"): route is not None and route.route_status == "ACTIVE",
            ("PENDING", "REJECTED"): True,
            ("SCHEDULED", "COLLECTED"): True,
            ("COLLECTED", "APPROVED"): latest is not None and latest.safety_status == "PASSED",
            ("COLLECTED", "REJECTED"): latest is not None and latest.safety_status == "FAILED",
        }
        if (current, target) not in allowed or not allowed[(current, target)]:
            if current == "COLLECTED" and target in {"APPROVED", "REJECTED"} and latest is None:
                raise ApiError(409, "inspection_required", "An inspection is required first.")
            raise ApiError(409, "invalid_transition", "That status change is not permitted.")
        if (
            target == "REJECTED"
            and db_session.scalar(
                select(Delivery.delivery_id).where(Delivery.donation_id == donation.donation_id)
            )
            is not None
        ):
            raise ApiError(
                409, "invalid_transition", "A donation with a delivery cannot be rejected."
            )
    elif user.user_role == "DRIVER":
        if (
            current != "SCHEDULED"
            or target != "COLLECTED"
            or route is None
            or route.designated_driver_user_id != user.user_id
        ):
            raise ApiError(409, "invalid_transition", "That status change is not permitted.")
    else:
        raise ApiError(403, "forbidden", "Your role cannot change donation status.")
    history = _append_history(db_session, donation, user.user_id, target, payload.note)
    from_status = donation.donation_status
    donation.donation_status = target
    atomic(db_session)
    db_session.refresh(history)
    return success(
        {
            "donation_id": donation.donation_id,
            "from_status": from_status,
            "to_status": target,
            "changed_at": iso_datetime(history.changed_at),
            "history_id": history.history_id,
        }
    )


@bp.get("/<int:donation_id>/history")
@require_auth
def donation_history(donation_id: int) -> Response:
    donation = get_donation(db(), actor(), donation_id)
    rows = (
        db()
        .execute(
            select(DonationStatusHistory)
            .where(DonationStatusHistory.donation_id == donation.donation_id)
            .order_by(
                DonationStatusHistory.changed_at.asc(), DonationStatusHistory.history_id.asc()
            )
        )
        .scalars()
        .all()
    )
    return success([history_payload(row) for row in rows])


@bp.get("/<int:donation_id>/items")
@require_auth
def list_items(donation_id: int) -> Response:
    donation = get_donation(db(), actor(), donation_id)
    rows = (
        db()
        .execute(
            select(DonationItem)
            .options(joinedload(DonationItem.category))
            .where(DonationItem.donation_id == donation.donation_id)
            .order_by(DonationItem.food_item_id.asc())
        )
        .scalars()
        .all()
    )
    return success([item_payload(db(), row) for row in rows])


@bp.post("/<int:donation_id>/items")
@require_roles("DONOR")
def create_item(donation_id: int) -> Response:
    db_session = db()
    donation = get_donation(db_session, actor(), donation_id)
    if donation.donor_user_id != actor().user_id:
        raise ApiError(404, "not_found", "The requested donation was not found.")
    if donation.donation_status not in {"PENDING", "SCHEDULED"}:
        raise ApiError(409, "invalid_transition", "Items cannot be added at this stage.")
    payload = parse_model(DonationItemCreate, request.get_json(silent=True))
    _validate_items(db_session, [payload])
    item = DonationItem(
        donation_id=donation.donation_id,
        category_id=payload.category_id,
        item_name=payload.item_name,
        quantity_kg=payload.quantity_kg,
        prepared_at=payload.prepared_at,
        best_before=payload.best_before,
    )
    db_session.add(item)
    atomic(db_session)
    db_session.refresh(item)
    return success(item_payload(db_session, item), status=201)


@bp.patch("/<int:donation_id>/items/<int:food_item_id>")
@require_auth
def patch_item(donation_id: int, food_item_id: int) -> Response:
    db_session = db()
    user = actor()
    donation = get_donation(db_session, user, donation_id)
    item = get_item(db_session, user, food_item_id)
    if item.donation_id != donation.donation_id:
        raise ApiError(404, "not_found", "The requested food item was not found.")
    if user.user_role == "DONOR":
        if donation.donor_user_id != user.user_id or donation.donation_status not in {
            "PENDING",
            "SCHEDULED",
        }:
            raise ApiError(409, "invalid_transition", "This item can no longer be edited.")
    elif user.user_role != "NGO_MANAGER":
        raise ApiError(403, "forbidden", "Your role cannot edit food items.")
    payload = parse_model(DonationItemPatch, request.get_json(silent=True))
    target_id = item.donation_id
    if "donation_id" in payload.model_fields_set and payload.donation_id is not None:
        target_id = payload.donation_id
    target = db_session.get(Donation, target_id)
    if target is None or donation_scope(user, db_session) is None:
        raise ApiError(422, "invalid_reference", "The target donation is not editable by you.")
    in_scope = db_session.scalar(
        select(Donation.donation_id).where(
            Donation.donation_id == target_id, donation_scope(user, db_session)
        )
    )
    if in_scope is None:
        raise ApiError(404, "not_found", "The target donation was not found.")
    if user.user_role == "DONOR" and target.donor_user_id != user.user_id:
        raise ApiError(422, "invalid_reference", "The target donation is not yours.")
    if user.user_role == "DONOR" and target.donation_status not in {"PENDING", "SCHEDULED"}:
        raise ApiError(409, "invalid_transition", "The target donation cannot receive items now.")
    for field in ("donation_id", "item_name", "quantity_kg", "best_before"):
        if field in payload.model_fields_set:
            setattr(item, field, getattr(payload, field))
    if item.prepared_at is not None and item.best_before <= item.prepared_at:
        raise ApiError(422, "validation_error", "best_before must be after prepared_at.")
    atomic(db_session)
    db_session.refresh(item)
    return success(item_payload(db_session, item))
