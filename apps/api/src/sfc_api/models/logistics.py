from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

DELIVERY_STATUSES = ("PLANNED", "IN_TRANSIT", "DELIVERED", "FAILED", "CANCELLED")


class Delivery(Base):
    __tablename__ = "delivery"

    delivery_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donation.donation_id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("route.route_id"), nullable=False)
    driver_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.user_id"), nullable=True
    )
    recipient_branch_id: Mapped[int] = mapped_column(ForeignKey("branch.branch_id"), nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(
        Enum(*DELIVERY_STATUSES, name="delivery_status", native_enum=True),
        nullable=True,
        default="PLANNED",
    )

    donation: Mapped[Donation] = relationship(back_populates="deliveries")
    route: Mapped[Route] = relationship(back_populates="deliveries")
    driver: Mapped[AppUser | None] = relationship(foreign_keys=[driver_user_id])
    recipient_branch: Mapped[Branch] = relationship(foreign_keys=[recipient_branch_id])
    items: Mapped[list[DeliveryItem]] = relationship(back_populates="delivery")
    review: Mapped[DeliveryReview | None] = relationship(back_populates="delivery", uselist=False)


class DeliveryItem(Base):
    __tablename__ = "delivery_item"

    delivery_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery.delivery_id"), nullable=False)
    food_item_id: Mapped[int] = mapped_column(
        ForeignKey("donation_item.food_item_id"), nullable=False
    )
    allocated_quantity_kg: Mapped[Decimal] = mapped_column(
        "quantity_delivered_kg", Numeric(8, 2), nullable=False
    )

    delivery: Mapped[Delivery] = relationship(back_populates="items")
    food_item: Mapped[DonationItem] = relationship(
        back_populates="delivery_items", foreign_keys=[food_item_id]
    )


class SpoilageRecord(Base):
    __tablename__ = "spoilage_record"

    spoilage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_item_id: Mapped[int] = mapped_column(
        ForeignKey("donation_item.food_item_id"), nullable=False
    )
    reported_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), nullable=False)
    quantity_kg: Mapped[Decimal] = mapped_column(
        "quantity_spoiled_kg", Numeric(8, 2), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    food_item: Mapped[DonationItem] = relationship(
        back_populates="spoilage_records", foreign_keys=[food_item_id]
    )
    reporter: Mapped[AppUser] = relationship(foreign_keys=[reported_by_user_id])


class DeliveryReview(Base):
    __tablename__ = "delivery_review"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(
        ForeignKey("delivery.delivery_id"), unique=True, nullable=False
    )
    reviewed_by_user_id: Mapped[int] = mapped_column(
        "reviewer_user_id", ForeignKey("app_user.user_id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column("quality_notes", Text, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    delivery: Mapped[Delivery] = relationship(back_populates="review")
    reviewer: Mapped[AppUser] = relationship(foreign_keys=[reviewed_by_user_id])


from .donations import Donation, DonationItem, Route  # noqa: E402
from .people import AppUser, Branch  # noqa: E402
