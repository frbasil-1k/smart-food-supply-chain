"""Quantity-based donation reconciliation shared by delivery and spoilage paths."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import (
    Delivery,
    DeliveryItem,
    Donation,
    DonationItem,
    DonationStatusHistory,
    SpoilageRecord,
)


def donation_totals(db: Session, donation_id: int) -> tuple[Decimal, Decimal, Decimal]:
    donated = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(DonationItem.quantity_kg), 0)).where(
                DonationItem.donation_id == donation_id
            )
        )
        or 0
    )
    delivered = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
            .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
            .join(DonationItem, DonationItem.food_item_id == DeliveryItem.food_item_id)
            .where(
                DonationItem.donation_id == donation_id,
                Delivery.delivery_status == "DELIVERED",
            )
        )
        or 0
    )
    spoiled = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(SpoilageRecord.quantity_kg), 0))
            .join(DonationItem, DonationItem.food_item_id == SpoilageRecord.food_item_id)
            .where(DonationItem.donation_id == donation_id)
        )
        or 0
    )
    return donated, delivered, spoiled


def recompute_donation(db: Session, donation_id: int, actor_id: int | None) -> Donation:
    donation = db.execute(
        select(Donation).where(Donation.donation_id == donation_id).with_for_update()
    ).scalar_one()
    donated, delivered, spoiled = donation_totals(db, donation_id)
    balance = donated - delivered - spoiled
    current = donation.donation_status
    target = current
    if balance == 0:
        target = "COMPLETED"
    elif delivered + spoiled > 0 and balance > 0:
        target = "PARTIALLY_DISTRIBUTED"
    if target != current and current not in {
        "PENDING",
        "SCHEDULED",
        "COLLECTED",
        "CANCELLED",
        "REJECTED",
    }:
        db.add(
            DonationStatusHistory(
                donation_id=donation_id,
                from_status=current,
                to_status=target,
                changed_by_user_id=actor_id,
                changed_at=func.now(),
                is_reconstructed=False,
                note="Recomputed from delivered and spoiled quantities",
            )
        )
        donation.donation_status = target
        db.flush()
    return donation


def item_committed_kg(db: Session, food_item_id: int) -> tuple[Decimal, Decimal, Decimal]:
    allocated = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0)).where(
                DeliveryItem.food_item_id == food_item_id
            )
        )
        or 0
    )
    delivered = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(DeliveryItem.allocated_quantity_kg), 0))
            .join(Delivery, Delivery.delivery_id == DeliveryItem.delivery_id)
            .where(
                DeliveryItem.food_item_id == food_item_id,
                Delivery.delivery_status == "DELIVERED",
            )
        )
        or 0
    )
    spoiled = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(SpoilageRecord.quantity_kg), 0)).where(
                SpoilageRecord.food_item_id == food_item_id
            )
        )
        or 0
    )
    return allocated, delivered, spoiled


def available_kg(db: Session, item: DonationItem) -> Decimal:
    allocated, _, spoiled = item_committed_kg(db, item.food_item_id)
    return max(Decimal(item.quantity_kg) - allocated - spoiled, Decimal("0"))


def remove_delivery_items(db: Session, delivery_id: int) -> None:
    db.execute(delete(DeliveryItem).where(DeliveryItem.delivery_id == delivery_id))
