"""Canonical row-level scope rules shared by every read and write path."""

from __future__ import annotations

from sqlalchemy import Select, and_, false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ..errors import ApiError
from ..models import (
    AppUser,
    Branch,
    Delivery,
    DeliveryItem,
    Donation,
    DonationItem,
    InspectionLog,
    Route,
    SpoilageRecord,
)


def managed_branch_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(select(Branch.branch_id).where(Branch.regional_manager_user_id == user_id)).all()
    )


def donation_scope(actor: AppUser, db: Session) -> ColumnElement[bool]:
    if actor.user_role == "DONOR":
        return Donation.donor_user_id == actor.user_id
    if actor.user_role == "DRIVER":
        route_ids = select(Route.route_id).where(Route.designated_driver_user_id == actor.user_id)
        delivery_donations = select(Delivery.donation_id).where(
            Delivery.driver_user_id == actor.user_id
        )
        return or_(
            Donation.pickup_route_id.in_(route_ids), Donation.donation_id.in_(delivery_donations)
        )
    if actor.user_role == "NGO_MANAGER":
        branch_ids = managed_branch_ids(db, actor.user_id)
        if not branch_ids:
            return false()
        branch_routes = select(Route.route_id).where(Route.managing_branch_id.in_(branch_ids))
        branch_donors = select(AppUser.user_id).where(AppUser.primary_branch_id.in_(branch_ids))
        return or_(
            Donation.pickup_route_id.in_(branch_routes),
            and_(Donation.pickup_route_id.is_(None), Donation.donor_user_id.in_(branch_donors)),
        )
    if actor.user_role == "SAFETY_INSPECTOR":
        inspected = select(InspectionLog.donation_id).where(
            InspectionLog.inspector_user_id == actor.user_id
        )
        conditions: list[ColumnElement[bool]] = [
            Donation.donation_id.in_(inspected),
            Donation.pickup_route_id.is_(None),
        ]
        if actor.primary_branch_id is not None:
            branch_routes = select(Route.route_id).where(
                Route.managing_branch_id == actor.primary_branch_id
            )
            conditions.append(Donation.pickup_route_id.in_(branch_routes))
        return or_(*conditions)
    return false()


def delivery_scope(actor: AppUser, db: Session) -> ColumnElement[bool]:
    if actor.user_role == "DONOR":
        return Delivery.donation_id.in_(
            select(Donation.donation_id).where(Donation.donor_user_id == actor.user_id)
        )
    if actor.user_role == "NGO_MANAGER":
        branch_ids = managed_branch_ids(db, actor.user_id)
        if not branch_ids:
            return false()
        branch_routes = select(Route.route_id).where(Route.managing_branch_id.in_(branch_ids))
        return or_(
            Delivery.recipient_branch_id.in_(branch_ids),
            Delivery.route_id.in_(branch_routes),
        )
    if actor.user_role == "DRIVER":
        return Delivery.driver_user_id == actor.user_id
    return false()


def inspection_scope(actor: AppUser, db: Session) -> ColumnElement[bool]:
    if actor.user_role == "DRIVER":
        delivery_donations = select(Delivery.donation_id).where(
            Delivery.driver_user_id == actor.user_id
        )
        return InspectionLog.donation_id.in_(delivery_donations)
    return InspectionLog.donation_id.in_(
        select(Donation.donation_id).where(donation_scope(actor, db))
    )


def spoilage_scope(actor: AppUser, db: Session) -> ColumnElement[bool]:
    scoped_items = select(DonationItem.food_item_id).where(
        DonationItem.donation_id.in_(select(Donation.donation_id).where(donation_scope(actor, db)))
    )
    if actor.user_role == "DRIVER":
        driver_items = select(DeliveryItem.food_item_id).where(
            DeliveryItem.delivery_id.in_(
                select(Delivery.delivery_id).where(Delivery.driver_user_id == actor.user_id)
            )
        )
        return SpoilageRecord.food_item_id.in_(driver_items)
    return SpoilageRecord.food_item_id.in_(scoped_items)


def _one[T](db: Session, stmt: Select[tuple[T]], label: str) -> T:
    value = db.execute(stmt).scalar_one_or_none()
    if value is None:
        raise ApiError(404, "not_found", f"The requested {label} was not found.")
    return value


def get_donation(db: Session, actor: AppUser, donation_id: int) -> Donation:
    return _one(
        db,
        select(Donation).where(Donation.donation_id == donation_id, donation_scope(actor, db)),
        "donation",
    )


def get_delivery(db: Session, actor: AppUser, delivery_id: int) -> Delivery:
    return _one(
        db,
        select(Delivery).where(Delivery.delivery_id == delivery_id, delivery_scope(actor, db)),
        "delivery",
    )


def get_item(db: Session, actor: AppUser, food_item_id: int) -> DonationItem:
    return _one(
        db,
        select(DonationItem).where(
            DonationItem.food_item_id == food_item_id,
            DonationItem.donation_id.in_(
                select(Donation.donation_id).where(donation_scope(actor, db))
            ),
        ),
        "food item",
    )


def get_inspection(db: Session, actor: AppUser, inspection_id: int) -> InspectionLog:
    return _one(
        db,
        select(InspectionLog).where(
            InspectionLog.inspection_id == inspection_id,
            inspection_scope(actor, db),
        ),
        "inspection",
    )


def get_spoilage(db: Session, actor: AppUser, spoilage_id: int) -> SpoilageRecord:
    return _one(
        db,
        select(SpoilageRecord).where(
            SpoilageRecord.spoilage_id == spoilage_id,
            spoilage_scope(actor, db),
        ),
        "spoilage record",
    )


def managed_route(db: Session, actor: AppUser, route_id: int) -> Route:
    branch_ids = managed_branch_ids(db, actor.user_id)
    if not branch_ids:
        raise ApiError(404, "not_found", "The requested route was not found.")
    return _one(
        db,
        select(Route).where(Route.route_id == route_id, Route.managing_branch_id.in_(branch_ids)),
        "route",
    )


def managed_branch(db: Session, actor: AppUser, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or branch.regional_manager_user_id != actor.user_id:
        raise ApiError(404, "not_found", "The requested branch was not found.")
    return branch
