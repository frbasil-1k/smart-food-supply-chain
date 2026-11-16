"""Role-scoped KPIs, reports, CSV exports and the proof-only activity feed."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from ..auth.middleware import require_auth, require_roles
from ..config import Settings
from ..errors import ApiError
from ..models import (
    AppUser,
    Branch,
    Delivery,
    DeliveryItem,
    DeliveryReview,
    Donation,
    DonationItem,
    DonationStatusHistory,
    DonorImpactView,
    DriverPerformanceView,
    InspectionLog,
    Route,
)
from ..responses import success
from ..services.common import decimal_str, iso_datetime
from ..services.reconciliation import donation_totals
from ..services.scope import donation_scope, managed_branch_ids
from ..services.serializers import (
    donor_impact_payload,
    driver_performance_payload,
    item_payload,
)
from .helpers import actor, db, filter_value, int_filter, page, paged_response

bp = Blueprint("reports", __name__, url_prefix="/api")


def _settings() -> Settings:
    return current_app.extensions["sfc_settings"]


def _now() -> datetime:
    return datetime.now(ZoneInfo(_settings().timezone)).replace(tzinfo=None)


def _report_response(data: Any, filename: str) -> Response:
    if request.args.get("export") == "csv":
        return _csv_response(data, filename)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    etag = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if request.headers.get("If-None-Match", "").strip('"') == etag:
        return Response(status=304)
    response = success(data)
    response.set_etag(etag)
    return response


def _csv_response(data: Any, filename: str) -> Response:
    rows = data if isinstance(data, list) else [data]
    if not rows:
        rows = [{}]
    keys: list[str] = []
    for row in rows:
        keys.extend(key for key in row if key not in keys)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(value, ensure_ascii=False, default=str)
                    if isinstance(value, (dict, list))
                    else value
                )
                for key, value in row.items()
            }
        )
    response = Response(output.getvalue(), content_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def _scoped_donations(user: AppUser) -> list[Donation]:
    db_session = db()
    return list(
        db_session.execute(
            select(Donation)
            .where(
                donation_scope(user, db_session),
                Donation.donation_status != "CANCELLED",
            )
            .options(
                joinedload(Donation.donor),
                joinedload(Donation.pickup_route),
                selectinload(Donation.items),
                selectinload(Donation.deliveries).selectinload(Delivery.items),
            )
            .order_by(Donation.donation_id.desc())
        )
        .scalars()
        .all()
    )


def _donor_rows(user: AppUser) -> list[dict[str, Any]]:
    db_session = db()
    grouped: dict[int, dict[str, Any]] = {}
    for donation in _scoped_donations(user):
        donated, delivered, spoiled = donation_totals(db_session, donation.donation_id)
        row = grouped.setdefault(
            donation.donor_user_id,
            {
                "donor_id": donation.donor_user_id,
                "donor_name": donation.donor.full_name if donation.donor else None,
                "email": donation.donor.email if donation.donor else None,
                "total_donations": 0,
                "donated": Decimal("0"),
                "delivered": Decimal("0"),
                "spoiled": Decimal("0"),
            },
        )
        row["total_donations"] += 1
        row["donated"] += donated
        row["delivered"] += delivered
        row["spoiled"] += spoiled
    result = []
    for row in sorted(grouped.values(), key=lambda item: (item["donor_name"] or "").lower()):
        balance = row["donated"] - row["delivered"] - row["spoiled"]
        result.append(
            {
                "donor_id": row["donor_id"],
                "donor_name": row["donor_name"],
                "email": row["email"],
                "total_donations": row["total_donations"],
                "total_donated_kg": decimal_str(row["donated"]),
                "delivered_kg": decimal_str(row["delivered"]),
                "spoiled_kg": decimal_str(row["spoiled"]),
                "undistributed_balance_kg": decimal_str(balance),
                "balance_kg": decimal_str(balance),
            }
        )
    return result


def _donor_items(user: AppUser, donor_id: int) -> list[dict[str, Any]]:
    db_session = db()
    rows = (
        db_session.execute(
            select(Donation)
            .where(Donation.donor_user_id == donor_id, donation_scope(user, db_session))
            .options(
                joinedload(Donation.pickup_route),
                selectinload(Donation.items).joinedload(DonationItem.category),
            )
            .order_by(Donation.donation_id.desc())
        )
        .scalars()
        .all()
    )
    result = []
    for donation in rows:
        for item in donation.items:
            result.append(
                {
                    "donation_id": donation.donation_id,
                    "donation_status": donation.donation_status,
                    "pickup_datetime": iso_datetime(donation.pickup_datetime),
                    "food_item": item_payload(db_session, item),
                }
            )
    return result


def _branch_delivery_filter(branch_ids: list[int]) -> Any:
    return or_(
        Delivery.recipient_branch_id.in_(branch_ids),
        Delivery.route_id.in_(
            select(Route.route_id).where(Route.managing_branch_id.in_(branch_ids))
        ),
    )


@bp.get("/reports/overview")
@require_auth
def overview() -> Response:
    db_session = db()
    user = actor()
    now = _now()
    if user.user_role == "DONOR":
        view = db_session.get(DonorImpactView, user.user_id)
        status_rows = db_session.execute(
            select(Donation.donation_status, func.count())
            .where(Donation.donor_user_id == user.user_id)
            .group_by(Donation.donation_status)
        ).all()
        return success(
            {
                "open_donations": sum(
                    int(count)
                    for status, count in status_rows
                    if status not in {"COMPLETED", "CANCELLED", "REJECTED"}
                ),
                "kg_donated": decimal_str(view.total_donated_kg if view else None),
                "kg_delivered": decimal_str(view.delivered_kg if view else None),
                "kg_spoiled": decimal_str(view.spoiled_kg if view else None),
                "balance_kg": decimal_str(view.undistributed_balance_kg if view else None),
                "donations_by_status": [
                    {"status": status, "count": int(count)} for status, count in status_rows
                ],
            }
        )
    if user.user_role == "NGO_MANAGER":
        branch_ids = managed_branch_ids(db_session, user.user_id)
        donations = _scoped_donations(user)
        ids = [row.donation_id for row in donations]
        awaiting = sum(1 for row in donations if row.donation_status in {"PENDING", "COLLECTED"})
        queue = sum(1 for row in donations if row.donation_status == "COLLECTED")
        today = now.date()
        transit = (
            db_session.scalar(
                select(func.count())
                .select_from(Delivery)
                .where(
                    Delivery.delivery_status == "IN_TRANSIT", _branch_delivery_filter(branch_ids)
                )
            )
            if branch_ids
            else 0
        )
        deliveries_today = (
            db_session.scalar(
                select(func.count())
                .select_from(Delivery)
                .where(
                    func.date(Delivery.scheduled_for) == today, _branch_delivery_filter(branch_ids)
                )
            )
            if branch_ids
            else 0
        )
        allocated = (
            db_session.scalar(
                select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
                .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
                .where(
                    Delivery.delivery_status.in_(("PLANNED", "IN_TRANSIT")),
                    Delivery.donation_id.in_(ids),
                )
            )
            if ids
            else 0
        )
        expiring = sum(
            1
            for row in donations
            for item in row.items
            if now < item.best_before <= now + timedelta(hours=48)
        )
        avg_rating = (
            db_session.scalar(
                select(func.avg(DeliveryReview.rating))
                .join(Delivery, Delivery.delivery_id == DeliveryReview.delivery_id)
                .where(_branch_delivery_filter(branch_ids))
            )
            if branch_ids
            else None
        )
        return success(
            {
                "donations_awaiting_review": awaiting,
                "inspections_pending": queue,
                "deliveries_in_transit": int(transit or 0),
                "deliveries_today": int(deliveries_today or 0),
                "kg_allocated_open": decimal_str(allocated),
                "expiring_within_48h": expiring,
                "avg_rating": decimal_str(avg_rating) if avg_rating is not None else "0.00",
            }
        )
    if user.user_role == "DRIVER":
        today = now.date()
        week_start = now - timedelta(days=7)
        assigned_today = db_session.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(
                Delivery.driver_user_id == user.user_id,
                Delivery.delivery_status.in_(("PLANNED", "IN_TRANSIT")),
                func.date(Delivery.scheduled_for) == today,
            )
        )
        transit = db_session.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(
                Delivery.driver_user_id == user.user_id, Delivery.delivery_status == "IN_TRANSIT"
            )
        )
        delivered = db_session.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(
                Delivery.driver_user_id == user.user_id,
                Delivery.delivery_status == "DELIVERED",
                Delivery.delivered_at >= week_start,
            )
        )
        kg = db_session.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
            .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
            .where(
                Delivery.driver_user_id == user.user_id,
                Delivery.delivery_status == "DELIVERED",
                Delivery.delivered_at >= week_start,
            )
        )
        next_delivery = db_session.execute(
            select(Delivery)
            .options(joinedload(Delivery.route), joinedload(Delivery.recipient_branch))
            .where(
                Delivery.driver_user_id == user.user_id,
                Delivery.delivery_status.in_(("PLANNED", "IN_TRANSIT")),
            )
            .order_by(Delivery.scheduled_for.asc(), Delivery.delivery_id.asc())
            .limit(1)
        ).scalar_one_or_none()
        return success(
            {
                "assigned_today": int(assigned_today or 0),
                "in_transit": int(transit or 0),
                "delivered_this_week": int(delivered or 0),
                "kg_delivered_this_week": decimal_str(kg),
                "next_delivery": (
                    {
                        "delivery_id": next_delivery.delivery_id,
                        "scheduled_for": iso_datetime(next_delivery.scheduled_for),
                        "recipient_branch": (
                            next_delivery.recipient_branch.branch_name
                            if next_delivery.recipient_branch
                            else None
                        ),
                    }
                    if next_delivery
                    else None
                ),
            }
        )
    donations = _scoped_donations(user)
    today = now.date()
    queue_size = sum(
        1
        for donation in donations
        if donation.donation_status == "COLLECTED"
        and not any(
            row.safety_status == "PASSED"
            for row in sorted(
                donation.inspections,
                key=lambda row: (row.inspected_at, row.inspection_id),
                reverse=True,
            )[:1]
        )
    )
    inspected_today = db_session.scalar(
        select(func.count())
        .select_from(InspectionLog)
        .where(
            InspectionLog.inspector_user_id == user.user_id,
            func.date(InspectionLog.inspected_at) == today,
        )
    )
    failed = db_session.scalar(
        select(func.count())
        .select_from(InspectionLog)
        .where(
            InspectionLog.inspector_user_id == user.user_id,
            InspectionLog.safety_status == "FAILED",
            InspectionLog.inspected_at >= now - timedelta(days=7),
        )
    )
    avg_temp = db_session.scalar(
        select(func.avg(InspectionLog.temperature_c)).where(
            InspectionLog.inspector_user_id == user.user_id,
            InspectionLog.inspected_at >= now - timedelta(days=7),
        )
    )
    return success(
        {
            "queue_size": queue_size,
            "inspected_today": int(inspected_today or 0),
            "failed_last_7d": int(failed or 0),
            "avg_temperature_7d": decimal_str(avg_temp) if avg_temp is not None else "0.00",
        }
    )


@bp.get("/reports/donors")
@require_roles("DONOR", "NGO_MANAGER")
def donor_report() -> Response:
    db_session = db()
    user = actor()
    if user.user_role == "DONOR":
        view = db_session.get(DonorImpactView, user.user_id)
        data = [
            (
                donor_impact_payload(view)
                if view
                else {
                    "donor_id": user.user_id,
                    "donor_name": user.full_name,
                    "total_donations": 0,
                    "total_donated_kg": "0.00",
                    "delivered_kg": "0.00",
                    "spoiled_kg": "0.00",
                    "undistributed_balance_kg": "0.00",
                    "balance_kg": "0.00",
                }
            )
        ]
    else:
        data = _donor_rows(user)
        donor_id = int_filter("donor_id")
        if donor_id:
            data = [row for row in data if row["donor_id"] == donor_id]
        q = filter_value("q")
        if q:
            data = [
                row
                for row in data
                if q.casefold() in str(row["donor_name"]).casefold()
                or q.casefold() in str(row["email"]).casefold()
            ]
    return _report_response(data, "donor-report")


@bp.get("/reports/donors/<int:donor_id>")
@require_roles("DONOR", "NGO_MANAGER")
def donor_report_detail(donor_id: int) -> Response:
    db_session = db()
    user = actor()
    if user.user_role == "DONOR" and donor_id != user.user_id:
        raise ApiError(404, "not_found", "The requested donor was not found.")
    if user.user_role == "DONOR":
        view = db_session.get(DonorImpactView, donor_id)
        if view is None and donor_id != user.user_id:
            raise ApiError(404, "not_found", "The requested donor was not found.")
        row = (
            donor_impact_payload(view)
            if view
            else {
                "donor_id": user.user_id,
                "donor_name": user.full_name,
                "total_donations": 0,
                "total_donated_kg": "0.00",
                "delivered_kg": "0.00",
                "spoiled_kg": "0.00",
                "undistributed_balance_kg": "0.00",
                "balance_kg": "0.00",
            }
        )
    else:
        rows = [row for row in _donor_rows(user) if row["donor_id"] == donor_id]
        if not rows:
            raise ApiError(404, "not_found", "The requested donor was not found.")
        row = rows[0]
    row = {**row, "items": _donor_items(user, donor_id)}
    return _report_response(row, f"donor-{donor_id}-report")


@bp.get("/reports/drivers")
@require_roles("NGO_MANAGER", "DRIVER")
def driver_report() -> Response:
    db_session = db()
    user = actor()
    if user.user_role == "DRIVER":
        view = db_session.get(DriverPerformanceView, user.user_id)
        data = [
            (
                driver_performance_payload(view)
                if view
                else {
                    "driver_id": user.user_id,
                    "driver_name": user.full_name,
                    "assigned_routes": 0,
                    "completed_deliveries": 0,
                    "delivered_quantity_kg": "0.00",
                }
            )
        ]
    else:
        branch_ids = managed_branch_ids(db_session, user.user_id)
        if not branch_ids:
            data = []
        else:
            drivers = (
                db_session.execute(
                    select(AppUser)
                    .where(AppUser.user_role == "DRIVER", AppUser.primary_branch_id.in_(branch_ids))
                    .order_by(AppUser.full_name)
                )
                .scalars()
                .all()
            )
            delivery_rows = db_session.execute(
                select(
                    Delivery.driver_user_id,
                    func.count(func.distinct(Delivery.delivery_id)),
                    func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0),
                )
                .join(DeliveryItem, DeliveryItem.delivery_id == Delivery.delivery_id)
                .join(Route, Route.route_id == Delivery.route_id)
                .where(
                    Delivery.delivery_status == "DELIVERED",
                    Route.managing_branch_id.in_(branch_ids),
                )
                .group_by(Delivery.driver_user_id)
            ).all()
            delivered = {row[0]: (int(row[1]), Decimal(row[2] or 0)) for row in delivery_rows}
            assigned = {
                row[0]: int(row[1])
                for row in db_session.execute(
                    select(Route.designated_driver_user_id, func.count())
                    .where(Route.managing_branch_id.in_(branch_ids))
                    .group_by(Route.designated_driver_user_id)
                ).all()
            }
            data = []
            for driver in drivers:
                count, kg = delivered.get(driver.user_id, (0, Decimal("0")))
                data.append(
                    {
                        "driver_id": driver.user_id,
                        "driver_name": driver.full_name,
                        "assigned_routes": assigned.get(driver.user_id, 0),
                        "completed_deliveries": count,
                        "delivered_quantity_kg": decimal_str(kg),
                    }
                )
    return _report_response(data, "driver-report")


@bp.get("/reports/branches")
@require_roles("NGO_MANAGER")
def branch_report() -> Response:
    db_session = db()
    user = actor()
    branch_ids = managed_branch_ids(db_session, user.user_id)
    if not branch_ids:
        return _report_response([], "branch-report")
    branches = (
        db_session.execute(
            select(Branch).where(Branch.branch_id.in_(branch_ids)).order_by(Branch.branch_name)
        )
        .scalars()
        .all()
    )
    donations = _scoped_donations(user)
    ratings = {
        row[0]: row[1]
        for row in db_session.execute(
            select(Delivery.recipient_branch_id, func.avg(DeliveryReview.rating))
            .join(DeliveryReview, DeliveryReview.delivery_id == Delivery.delivery_id)
            .where(Delivery.recipient_branch_id.in_(branch_ids))
            .group_by(Delivery.recipient_branch_id)
        ).all()
    }
    data = []
    for branch in branches:
        totals = [Decimal("0"), Decimal("0"), Decimal("0")]
        count = 0
        for donation in donations:
            attribution = (
                donation.pickup_route.managing_branch_id
                if donation.pickup_route
                else (donation.donor.primary_branch_id if donation.donor else None)
            )
            if attribution != branch.branch_id:
                continue
            donated, delivered, spoiled = donation_totals(db_session, donation.donation_id)
            count += 1
            totals[0] += donated
            totals[1] += delivered
            totals[2] += spoiled
        data.append(
            {
                "branch_id": branch.branch_id,
                "branch_name": branch.branch_name,
                "total_donations": count,
                "total_donated_kg": decimal_str(totals[0]),
                "delivered_kg": decimal_str(totals[1]),
                "spoiled_kg": decimal_str(totals[2]),
                "balance_kg": decimal_str(totals[0] - totals[1] - totals[2]),
                "avg_rating": (
                    decimal_str(ratings[branch.branch_id])
                    if ratings.get(branch.branch_id) is not None
                    else "0.00"
                ),
            }
        )
    return _report_response(data, "branch-report")


@bp.get("/reports/freshness")
@require_roles("DONOR", "NGO_MANAGER", "SAFETY_INSPECTOR")
def freshness_report() -> Response:
    db_session = db()
    user = actor()
    now = _now()
    try:
        within_hours = max(1, min(720, int(request.args.get("within_hours", 48))))
    except ValueError:
        within_hours = 48
    items = (
        db_session.execute(
            select(DonationItem)
            .join(Donation, Donation.donation_id == DonationItem.donation_id)
            .where(
                donation_scope(user, db_session),
                DonationItem.best_before <= now + timedelta(hours=within_hours),
            )
            .options(joinedload(DonationItem.category))
            .order_by(DonationItem.best_before.asc())
        )
        .scalars()
        .all()
    )
    data = []
    for item in items:
        open_allocated = db_session.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
            .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
            .where(
                DeliveryItem.food_item_id == item.food_item_id,
                Delivery.delivery_status.in_(("PLANNED", "IN_TRANSIT")),
            )
        ) or Decimal("0")
        hours = (item.best_before - now).total_seconds() / 3600
        data.append(
            {
                "food_item_id": item.food_item_id,
                "donation_id": item.donation_id,
                "item_name": item.item_name,
                "category": item.category.category_name if item.category else None,
                "quantity_kg": decimal_str(item.quantity_kg),
                "best_before": iso_datetime(item.best_before),
                "hours_remaining": f"{hours:.1f}",
                "is_expired": hours < 0,
                "open_allocated_kg": decimal_str(open_allocated),
            }
        )
    return _report_response(data, "freshness-report")


@bp.get("/activity")
@require_auth
def activity() -> Response:
    db_session = db()
    user = actor()
    donations = _scoped_donations(user)
    ids = [row.donation_id for row in donations]
    if not ids:
        return paged_response([], 1, 25, 0)
    events: list[dict[str, Any]] = []
    history = (
        db_session.execute(
            select(DonationStatusHistory)
            .options(joinedload(DonationStatusHistory.changed_by))
            .where(DonationStatusHistory.donation_id.in_(ids))
        )
        .scalars()
        .all()
    )
    for history_row in history:
        events.append(
            {
                "event_type": "donation_status",
                "timestamp": iso_datetime(history_row.changed_at),
                "donation_id": history_row.donation_id,
                "description": (
                    "Status reconstructed from current state"
                    if history_row.is_reconstructed
                    else (
                        f"Donation {history_row.from_status or 'created'}"
                        f" -> {history_row.to_status}"
                    )
                ),
                "actor": history_row.changed_by.full_name if history_row.changed_by else None,
                "sort_key": history_row.changed_at.timestamp() if history_row.changed_at else 0,
            }
        )
    inspections = (
        db_session.execute(
            select(InspectionLog)
            .options(joinedload(InspectionLog.inspector))
            .where(InspectionLog.donation_id.in_(ids))
        )
        .scalars()
        .all()
    )
    for inspection_row in inspections:
        events.append(
            {
                "event_type": "inspection",
                "timestamp": iso_datetime(inspection_row.inspected_at),
                "donation_id": inspection_row.donation_id,
                "description": f"Inspection {inspection_row.safety_status}",
                "actor": inspection_row.inspector.full_name if inspection_row.inspector else None,
                "sort_key": (
                    inspection_row.inspected_at.timestamp() if inspection_row.inspected_at else 0
                ),
            }
        )
    deliveries = (
        db_session.execute(
            select(Delivery).where(
                Delivery.donation_id.in_(ids), Delivery.delivered_at.is_not(None)
            )
        )
        .scalars()
        .all()
    )
    for delivery_row in deliveries:
        events.append(
            {
                "event_type": "delivery_delivered",
                "timestamp": iso_datetime(delivery_row.delivered_at),
                "donation_id": delivery_row.donation_id,
                "description": f"Delivery {delivery_row.delivery_id} delivered",
                "actor": None,
                "sort_key": (
                    delivery_row.delivered_at.timestamp() if delivery_row.delivered_at else 0
                ),
            }
        )
    events.sort(key=lambda event: event.pop("sort_key", 0), reverse=True)
    page_number, page_size = page()
    start = (page_number - 1) * page_size
    return paged_response(events[start : start + page_size], page_number, page_size, len(events))
