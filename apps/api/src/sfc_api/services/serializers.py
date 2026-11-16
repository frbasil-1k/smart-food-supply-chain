"""Dictionary serialisers implementing the public API contract."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Branch,
    Delivery,
    DeliveryItem,
    DeliveryReview,
    Donation,
    DonationItem,
    DonationStatusHistory,
    DonorImpactView,
    DriverPerformanceView,
    FoodCategory,
    InspectionLog,
    Organization,
    Route,
    RouteAssignment,
    SpoilageRecord,
    UserCredential,
)
from .common import decimal_str, iso_date, iso_datetime


def branch_payload(
    branch: Branch,
    *,
    organization_name: str | None = None,
    manager_name: str | None = None,
) -> dict[str, Any]:
    return {
        "branch_id": branch.branch_id,
        "branch_name": branch.branch_name,
        "organization": {
            "organization_id": branch.organization_id,
            "organization_name": organization_name
            or (branch.organization.organization_name if branch.organization else None),
        },
        "address": branch.address,
        "pincode": branch.pincode,
        "contact_no": branch.contact_no,
        "established_date": iso_date(branch.established_date),
        "regional_manager": (
            {
                "user_id": branch.regional_manager_user_id,
                "full_name": manager_name
                or (branch.regional_manager.full_name if branch.regional_manager else None),
            }
            if branch.regional_manager_user_id
            else None
        ),
    }


def organization_payload(org: Organization) -> dict[str, Any]:
    return {
        "organization_id": org.organization_id,
        "organization_name": org.organization_name,
        "hq_address": org.hq_address,
        "hq_pincode": org.hq_pincode,
        "hq_contact_no": org.hq_contact_no,
    }


def user_payload(user: Any, *, credential: UserCredential | None = None) -> dict[str, Any]:
    branch = user.primary_branch
    payload: dict[str, Any] = {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.user_role,
        "account_status": user.account_status,
        "primary_branch_id": branch.branch_id if branch is not None else None,
        "branch_name": branch.branch_name if branch is not None else None,
        "primary_branch": (
            {"branch_id": branch.branch_id, "branch_name": branch.branch_name}
            if branch is not None
            else None
        ),
        "supervisor_user_id": user.supervisor_user_id,
    }
    if credential is not None:
        payload["must_change_password"] = bool(credential.must_change_password)
        payload["last_login_at"] = iso_datetime(credential.last_login_at)
    return payload


def route_payload(route: Route) -> dict[str, Any]:
    return {
        "route_id": route.route_id,
        "managing_branch": {
            "branch_id": route.managing_branch_id,
            "branch_name": route.managing_branch.branch_name if route.managing_branch else None,
        },
        "designated_driver": {
            "user_id": route.designated_driver_user_id,
            "full_name": route.designated_driver.full_name if route.designated_driver else None,
        },
        "coverage_area": {
            "coverage_area_id": route.coverage_area_id,
            "area_name": route.coverage_area.area_name if route.coverage_area else None,
            "city": route.coverage_area.city if route.coverage_area else None,
        },
        "route_type": route.route_type,
        "route_status": route.route_status,
    }


def assignment_payload(assignment: RouteAssignment) -> dict[str, Any]:
    return {
        "user_id": assignment.user_id,
        "route_id": assignment.route_id,
        "route": route_payload(assignment.route) if assignment.route else None,
        "user": (
            {
                "user_id": assignment.user.user_id,
                "full_name": assignment.user.full_name,
            }
            if assignment.user
            else None
        ),
        "hours_per_week": decimal_str(assignment.hours_per_week),
        "assigned_date": iso_date(assignment.assigned_date),
    }


def category_payload(category: FoodCategory) -> dict[str, Any]:
    return {"category_id": category.category_id, "category_name": category.category_name}


def history_payload(row: DonationStatusHistory) -> dict[str, Any]:
    return {
        "history_id": row.history_id,
        "donation_id": row.donation_id,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "changed_by": (
            {"user_id": row.changed_by_user_id, "full_name": row.changed_by.full_name}
            if row.changed_by is not None
            else None
        ),
        "changed_at": iso_datetime(row.changed_at),
        "is_reconstructed": bool(row.is_reconstructed),
        "note": row.note,
    }


def donation_summary(donation: Donation) -> dict[str, Any]:
    items = donation.items or []
    total = sum((item.quantity_kg for item in items), Decimal("0"))
    return {
        "donation_id": donation.donation_id,
        "donor": {
            "user_id": donation.donor_user_id,
            "full_name": donation.donor.full_name if donation.donor else None,
        },
        "pickup_route": (
            {
                "route_id": donation.pickup_route.route_id,
                "managing_branch_id": donation.pickup_route.managing_branch_id,
                "designated_driver_user_id": donation.pickup_route.designated_driver_user_id,
            }
            if donation.pickup_route is not None
            else None
        ),
        "pickup_datetime": iso_datetime(donation.pickup_datetime),
        "pickup_address": donation.pickup_address,
        "pickup_pincode": donation.pickup_pincode,
        "pickup_contact": donation.pickup_contact,
        "status": donation.donation_status,
        "urgency": donation.urgency_level,
        "item_count": len(items),
        "total_quantity_kg": decimal_str(total),
    }


def item_quantities(db: Session, item: DonationItem) -> dict[str, str]:
    allocated = db.scalar(
        select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0)).where(
            DeliveryItem.food_item_id == item.food_item_id
        )
    ) or Decimal("0")
    delivered = db.scalar(
        select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
        .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
        .where(
            DeliveryItem.food_item_id == item.food_item_id,
            Delivery.delivery_status == "DELIVERED",
        )
    ) or Decimal("0")
    spoiled = db.scalar(
        select(func.coalesce(func.sum(SpoilageRecord.quantity_kg), 0)).where(
            SpoilageRecord.food_item_id == item.food_item_id
        )
    ) or Decimal("0")
    available = Decimal(item.quantity_kg) - Decimal(allocated) - Decimal(spoiled)
    return {
        "quantity_kg": decimal_str(item.quantity_kg),
        "allocated_kg": decimal_str(allocated),
        "delivered_kg": decimal_str(delivered),
        "spoiled_kg": decimal_str(spoiled),
        "available_kg": decimal_str(max(available, Decimal("0"))),
    }


def item_payload(db: Session, item: DonationItem) -> dict[str, Any]:
    return {
        "food_item_id": item.food_item_id,
        "donation_id": item.donation_id,
        "category": category_payload(item.category) if item.category else None,
        "item_name": item.item_name,
        "prepared_at": iso_datetime(item.prepared_at),
        "best_before": iso_datetime(item.best_before),
        **item_quantities(db, item),
    }


def inspection_payload(row: InspectionLog) -> dict[str, Any]:
    return {
        "inspection_id": row.inspection_id,
        "donation_id": row.donation_id,
        "inspector": {
            "user_id": row.inspector_user_id,
            "full_name": row.inspector.full_name if row.inspector else None,
        },
        "inspected_at": iso_datetime(row.inspected_at),
        "temperature_c": decimal_str(row.temperature_c) if row.temperature_c is not None else None,
        "packaging_integrity": row.packaging_integrity,
        "safety_status": row.safety_status,
        "remarks": row.remarks,
    }


def review_payload(row: DeliveryReview) -> dict[str, Any]:
    return {
        "review_id": row.review_id,
        "delivery_id": row.delivery_id,
        "reviewed_by": {
            "user_id": row.reviewed_by_user_id,
            "full_name": row.reviewer.full_name if row.reviewer else None,
        },
        "rating": row.rating,
        "quality_notes": row.comment,
        "review_date": iso_datetime(row.review_date),
    }


def delivery_item_payload(item: DeliveryItem) -> dict[str, Any]:
    return {
        "delivery_item_id": item.delivery_item_id,
        "food_item_id": item.food_item_id,
        "item_name": item.food_item.item_name if item.food_item else None,
        "quantity_delivered_kg": decimal_str(item.allocated_quantity_kg),
    }


def delivery_payload(delivery: Delivery, *, detail: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "delivery_id": delivery.delivery_id,
        "donation": {
            "donation_id": delivery.donation_id,
            "status": delivery.donation.donation_status if delivery.donation else None,
            "donor": (
                {
                    "user_id": delivery.donation.donor_user_id,
                    "full_name": (
                        delivery.donation.donor.full_name
                        if delivery.donation and delivery.donation.donor
                        else None
                    ),
                }
                if delivery.donation
                else None
            ),
        },
        "route": {
            "route_id": delivery.route_id,
            "route_type": delivery.route.route_type if delivery.route else None,
            "managing_branch_id": delivery.route.managing_branch_id if delivery.route else None,
        },
        "driver": (
            {"user_id": delivery.driver_user_id, "full_name": delivery.driver.full_name}
            if delivery.driver is not None
            else None
        ),
        "recipient_branch": {
            "branch_id": delivery.recipient_branch_id,
            "branch_name": (
                delivery.recipient_branch.branch_name if delivery.recipient_branch else None
            ),
        },
        "scheduled_for": iso_datetime(delivery.scheduled_for),
        "delivered_at": iso_datetime(delivery.delivered_at),
        "status": delivery.delivery_status,
    }
    if detail:
        payload["items"] = [delivery_item_payload(item) for item in delivery.items]
        payload["review"] = review_payload(delivery.review) if delivery.review else None
    return payload


def spoilage_payload(row: SpoilageRecord) -> dict[str, Any]:
    return {
        "spoilage_id": row.spoilage_id,
        "food_item_id": row.food_item_id,
        "item_name": row.food_item.item_name if row.food_item else None,
        "donation_id": row.food_item.donation_id if row.food_item else None,
        "reported_by": {
            "user_id": row.reported_by_user_id,
            "full_name": row.reporter.full_name if row.reporter else None,
        },
        "quantity_spoiled_kg": decimal_str(row.quantity_kg),
        "reason": row.reason,
        "reported_at": iso_datetime(row.reported_at),
    }


def donation_detail(db: Session, donation: Donation) -> dict[str, Any]:
    latest = db.execute(
        select(InspectionLog)
        .where(InspectionLog.donation_id == donation.donation_id)
        .order_by(InspectionLog.inspected_at.desc(), InspectionLog.inspection_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    payload = donation_summary(donation)
    history = sorted(
        donation.history,
        key=lambda row: (row.changed_at.timestamp() if row.changed_at else 0, row.history_id),
    )
    payload.update(
        {
            "items": [item_payload(db, item) for item in donation.items],
            "latest_inspection": inspection_payload(latest) if latest else None,
            "deliveries": [delivery_payload(row) for row in donation.deliveries],
            "history": [history_payload(row) for row in history],
        }
    )
    return payload


def donor_impact_payload(row: DonorImpactView) -> dict[str, Any]:
    return {
        "donor_id": row.donor_id,
        "donor_name": row.donor_name,
        "total_donations": row.total_donations,
        "total_donated_kg": decimal_str(row.total_donated_kg),
        "delivered_kg": decimal_str(row.delivered_kg),
        "spoiled_kg": decimal_str(row.spoiled_kg),
        "undistributed_balance_kg": decimal_str(row.undistributed_balance_kg),
        "balance_kg": decimal_str(row.undistributed_balance_kg),
    }


def driver_performance_payload(row: DriverPerformanceView) -> dict[str, Any]:
    return {
        "driver_id": row.driver_id,
        "driver_name": row.driver_name,
        "assigned_routes": row.assigned_routes,
        "completed_deliveries": row.completed_deliveries,
        "delivered_quantity_kg": decimal_str(row.delivered_quantity_kg),
    }
