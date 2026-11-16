"""Pydantic v2 request models. Responses are serialised by services/serializers."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

DEFAULT_ZONE = ZoneInfo("Asia/Kolkata")
Quantity = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]
Rating = Annotated[int, Field(ge=1, le=5)]
Email = Annotated[str, StringConstraints(min_length=5, max_length=150)]
Phone = Annotated[str, StringConstraints(min_length=7, max_length=15)]
Pincode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[1-9][0-9]{5}$")]
PickupContact = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+91[6-9][0-9]{9}$")
]
USER_ROLE = Literal["DONOR", "NGO_MANAGER", "DRIVER", "SAFETY_INSPECTOR"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _to_ist(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid ISO-8601 datetime") from exc
    if not isinstance(value, datetime):
        return value  # Pydantic will report the type error.
    if value.tzinfo is None:
        value = value.replace(tzinfo=DEFAULT_ZONE)
    return value.astimezone(DEFAULT_ZONE).replace(tzinfo=None)


def _email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("invalid email address")
    return value


def _phone(value: str) -> str:
    compact = re.sub(r"[\s\-()]", "", value)
    if not re.fullmatch(r"\+?[0-9]{7,15}", compact):
        raise ValueError("invalid phone number")
    return compact


def _optional_phone(value: str | None) -> str | None:
    return None if value is None else _phone(value)


class LoginRequest(StrictModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)

    _normalise_email = field_validator("email")(_email)


class ActivateRequest(StrictModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=128)


class ResetConfirmRequest(StrictModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class AccountStatusRequest(StrictModel):
    account_status: Literal["ACTIVE", "INACTIVE"]


class DonationItemCreate(StrictModel):
    category_id: int = Field(gt=0)
    item_name: str = Field(min_length=1, max_length=150)
    quantity_kg: Quantity
    prepared_at: datetime | None = None
    best_before: datetime

    _normalise_prepared = field_validator("prepared_at", mode="before")(_to_ist)
    _normalise_best = field_validator("best_before", mode="before")(_to_ist)


class DonationCreate(StrictModel):
    pickup_route_id: int | None = Field(default=None, gt=0)
    pickup_datetime: datetime
    pickup_address: str = Field(min_length=5, max_length=255)
    pickup_pincode: Pincode
    pickup_contact: PickupContact
    urgency_level: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"
    items: list[DonationItemCreate] = Field(min_length=1, max_length=50)

    _normalise_pickup = field_validator("pickup_datetime", mode="before")(_to_ist)


class DonationPatch(StrictModel):
    pickup_datetime: datetime | None = None
    pickup_address: str | None = Field(default=None, min_length=5, max_length=255)
    pickup_pincode: Pincode | None = None
    pickup_contact: PickupContact | None = None
    urgency_level: Literal["LOW", "NORMAL", "HIGH"] | None = None

    _normalise_pickup = field_validator("pickup_datetime", mode="before")(_to_ist)


class DonationRoutePatch(StrictModel):
    pickup_route_id: int = Field(gt=0)


class DonationStatusPatch(StrictModel):
    target_status: Literal[
        "SCHEDULED",
        "COLLECTED",
        "APPROVED",
        "REJECTED",
        "CANCELLED",
    ]
    note: str | None = Field(default=None, max_length=255)


class DonationItemPatch(StrictModel):
    donation_id: int | None = Field(default=None, gt=0)
    item_name: str | None = Field(default=None, min_length=1, max_length=150)
    quantity_kg: Quantity | None = None
    best_before: datetime | None = None

    _normalise_best = field_validator("best_before", mode="before")(_to_ist)


class InspectionCreate(StrictModel):
    donation_id: int | None = Field(default=None, gt=0)
    temperature_c: Decimal | None = Field(
        default=None, ge=-50, le=100, max_digits=5, decimal_places=2
    )
    packaging_integrity: Literal["INTACT", "DAMAGED", "NOT_APPLICABLE"]
    safety_status: Literal["PASSED", "FAILED", "NEEDS_REVIEW"]
    remarks: str | None = Field(default=None, max_length=1000)


class DeliveryCreateItem(StrictModel):
    food_item_id: int = Field(gt=0)
    quantity_delivered_kg: Quantity


class DeliveryCreate(StrictModel):
    donation_id: int = Field(gt=0)
    route_id: int = Field(gt=0)
    recipient_branch_id: int = Field(gt=0)
    driver_user_id: int | None = Field(default=None, gt=0)
    scheduled_for: datetime | None = None
    items: list[DeliveryCreateItem] = Field(min_length=1, max_length=50)

    _normalise_scheduled = field_validator("scheduled_for", mode="before")(_to_ist)


class DeliveryPatch(StrictModel):
    driver_user_id: int | None = Field(default=None, gt=0)
    scheduled_for: datetime | None = None

    _normalise_scheduled = field_validator("scheduled_for", mode="before")(_to_ist)


class DeliveryStatusPatch(StrictModel):
    target_status: Literal["IN_TRANSIT", "DELIVERED", "FAILED", "CANCELLED"]


class DeliveryItemCreate(StrictModel):
    food_item_id: int = Field(gt=0)
    quantity_delivered_kg: Quantity


class DeliveryItemPatch(StrictModel):
    quantity_delivered_kg: Quantity


class ReviewCreate(StrictModel):
    rating: Rating
    quality_notes: str | None = Field(default=None, max_length=1000)


class SpoilageCreate(StrictModel):
    food_item_id: int = Field(gt=0)
    quantity_spoiled_kg: Quantity
    reason: str = Field(min_length=3, max_length=255)


class BranchCreate(StrictModel):
    organization_id: int = Field(gt=0)
    branch_name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    pincode: Pincode
    contact_no: Phone
    established_date: date


class BranchPatch(StrictModel):
    branch_name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    pincode: Pincode | None = None
    contact_no: Phone | None = None


class RouteCreate(StrictModel):
    managing_branch_id: int = Field(gt=0)
    designated_driver_user_id: int = Field(gt=0)
    coverage_area_id: int = Field(gt=0)
    route_type: Literal["PICKUP", "DISTRIBUTION", "MIXED"]
    route_status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"


class RoutePatch(StrictModel):
    designated_driver_user_id: int | None = Field(default=None, gt=0)
    coverage_area_id: int | None = Field(default=None, gt=0)
    route_type: Literal["PICKUP", "DISTRIBUTION", "MIXED"] | None = None
    route_status: Literal["ACTIVE", "INACTIVE"] | None = None


class RouteAssignmentCreate(StrictModel):
    user_id: int = Field(gt=0)
    hours_per_week: Decimal = Field(gt=0, le=168, max_digits=5, decimal_places=2)
    assigned_date: date


class TopRouteAssignmentCreate(RouteAssignmentCreate):
    route_id: int = Field(gt=0)


class DependentCreate(StrictModel):
    full_name: str = Field(min_length=1, max_length=100)
    relationship: str = Field(min_length=1, max_length=50)
    date_of_birth: date | None = None
    phone: Phone | None = None

    _normalise_phone = field_validator("phone")(_optional_phone)


class DependentPatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    relationship: str | None = Field(default=None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    phone: Phone | None = None

    _normalise_phone = field_validator("phone")(_optional_phone)
