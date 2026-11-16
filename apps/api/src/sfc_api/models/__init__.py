"""Approved SQLAlchemy mappings for the Step 7 schema.

No metadata.create_all(), DDL or migration is performed here. The mappings
describe the existing 18 tables and 3 views only.
"""

from __future__ import annotations

from .base import Base, ViewBase
from .donations import (
    DONATION_STATUSES,
    URGENCY_LEVELS,
    CoverageArea,
    Donation,
    DonationItem,
    DonationStatusHistory,
    FoodCategory,
    InspectionLog,
    Route,
    RouteAssignment,
)
from .logistics import (
    DELIVERY_STATUSES,
    Delivery,
    DeliveryItem,
    DeliveryReview,
    SpoilageRecord,
)
from .people import (
    ACCOUNT_STATUSES,
    USER_ROLES,
    AppUser,
    Branch,
    Dependent,
    Organization,
    UserCredential,
)
from .views import DonorImpactView, DonorSustainabilityView, DriverPerformanceView

__all__ = [
    "ACCOUNT_STATUSES",
    "DELIVERY_STATUSES",
    "DONATION_STATUSES",
    "URGENCY_LEVELS",
    "USER_ROLES",
    "AppUser",
    "Base",
    "Branch",
    "CoverageArea",
    "Delivery",
    "DeliveryItem",
    "DeliveryReview",
    "Dependent",
    "Donation",
    "DonationItem",
    "DonationStatusHistory",
    "DonorImpactView",
    "DonorSustainabilityView",
    "DriverPerformanceView",
    "FoodCategory",
    "InspectionLog",
    "Organization",
    "Route",
    "RouteAssignment",
    "SpoilageRecord",
    "UserCredential",
    "ViewBase",
]
