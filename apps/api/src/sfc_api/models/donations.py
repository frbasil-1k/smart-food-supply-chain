from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

DONATION_STATUSES = (
    "PENDING",
    "SCHEDULED",
    "COLLECTED",
    "APPROVED",
    "REJECTED",
    "PARTIALLY_DISTRIBUTED",
    "COMPLETED",
    "CANCELLED",
)
URGENCY_LEVELS = ("LOW", "NORMAL", "HIGH")
ROUTE_TYPES = ("PICKUP", "DISTRIBUTION", "MIXED")
ROUTE_STATUSES = ("ACTIVE", "INACTIVE")


class CoverageArea(Base):
    __tablename__ = "coverage_area"

    coverage_area_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)


class FoodCategory(Base):
    __tablename__ = "food_category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)


class Route(Base):
    __tablename__ = "route"

    route_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    managing_branch_id: Mapped[int] = mapped_column(ForeignKey("branch.branch_id"), nullable=False)
    designated_driver_user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.user_id"), nullable=False
    )
    coverage_area_id: Mapped[int] = mapped_column(
        ForeignKey("coverage_area.coverage_area_id"), nullable=False
    )
    route_type: Mapped[str] = mapped_column(
        Enum(*ROUTE_TYPES, name="route_type", native_enum=True), nullable=False
    )
    route_status: Mapped[str | None] = mapped_column(
        Enum(*ROUTE_STATUSES, name="route_status", native_enum=True),
        nullable=True,
        default="ACTIVE",
    )

    managing_branch: Mapped[Branch] = relationship(back_populates="routes")
    designated_driver: Mapped[AppUser] = relationship(foreign_keys=[designated_driver_user_id])
    coverage_area: Mapped[CoverageArea] = relationship()
    assignments: Mapped[list[RouteAssignment]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )
    deliveries: Mapped[list[Delivery]] = relationship(back_populates="route")


class RouteAssignment(Base):
    __tablename__ = "route_assignment"

    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("route.route_id"), primary_key=True)
    hours_per_week: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)

    route: Mapped[Route] = relationship(back_populates="assignments")
    user: Mapped[AppUser] = relationship(foreign_keys=[user_id])


class Donation(Base):
    __tablename__ = "donation"

    donation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    donor_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), nullable=False)
    pickup_route_id: Mapped[int | None] = mapped_column(ForeignKey("route.route_id"), nullable=True)
    pickup_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pickup_contact: Mapped[str | None] = mapped_column(String(15), nullable=True)
    donation_status: Mapped[str | None] = mapped_column(
        Enum(*DONATION_STATUSES, name="donation_status", native_enum=True),
        nullable=True,
        default="PENDING",
    )
    urgency_level: Mapped[str | None] = mapped_column(
        Enum(*URGENCY_LEVELS, name="urgency_level", native_enum=True),
        nullable=True,
        default="NORMAL",
    )

    donor: Mapped[AppUser] = relationship(back_populates="donations", foreign_keys=[donor_user_id])
    pickup_route: Mapped[Route | None] = relationship(foreign_keys=[pickup_route_id])
    items: Mapped[list[DonationItem]] = relationship(back_populates="donation")
    history: Mapped[list[DonationStatusHistory]] = relationship(back_populates="donation")
    inspections: Mapped[list[InspectionLog]] = relationship(back_populates="donation")
    deliveries: Mapped[list[Delivery]] = relationship(back_populates="donation")


class DonationItem(Base):
    __tablename__ = "donation_item"

    food_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donation.donation_id"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("food_category.category_id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    best_before: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    donation: Mapped[Donation] = relationship(back_populates="items")
    category: Mapped[FoodCategory] = relationship()
    spoilage_records: Mapped[list[SpoilageRecord]] = relationship(
        back_populates="food_item", foreign_keys="SpoilageRecord.food_item_id"
    )
    delivery_items: Mapped[list[DeliveryItem]] = relationship(
        back_populates="food_item", foreign_keys="DeliveryItem.food_item_id"
    )


class DonationStatusHistory(Base):
    __tablename__ = "donation_status_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donation.donation_id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(
        Enum(*DONATION_STATUSES, name="history_from_status", native_enum=True), nullable=True
    )
    to_status: Mapped[str] = mapped_column(
        Enum(*DONATION_STATUSES, name="history_to_status", native_enum=True), nullable=False
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.user_id"), nullable=True
    )
    changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_reconstructed: Mapped[bool] = mapped_column(nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reconstructed_donation_id: Mapped[int | None] = mapped_column(
        Integer,
        Computed("if((is_reconstructed = 1),donation_id,NULL)", persisted=True),
        nullable=True,
    )

    donation: Mapped[Donation] = relationship(back_populates="history")
    changed_by: Mapped[AppUser | None] = relationship(foreign_keys=[changed_by_user_id])


class InspectionLog(Base):
    __tablename__ = "inspection_log"

    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donation.donation_id"), nullable=False)
    inspector_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    packaging_integrity: Mapped[str] = mapped_column(
        Enum("INTACT", "DAMAGED", "NOT_APPLICABLE", name="packaging_integrity"),
        nullable=False,
    )
    safety_status: Mapped[str] = mapped_column(
        Enum("PASSED", "FAILED", "NEEDS_REVIEW", name="safety_status"), nullable=False
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    donation: Mapped[Donation] = relationship(back_populates="inspections")
    inspector: Mapped[AppUser] = relationship(foreign_keys=[inspector_user_id])


from .logistics import Delivery, DeliveryItem, SpoilageRecord  # noqa: E402
from .people import AppUser, Branch  # noqa: E402
