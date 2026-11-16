"""Bounded reference-data lookups used by donation and route forms."""

from __future__ import annotations

from flask import Blueprint, Response
from sqlalchemy import select

from ..auth.middleware import require_auth
from ..models import CoverageArea, FoodCategory, Organization
from ..responses import success
from ..services.serializers import category_payload, organization_payload
from .helpers import db

bp = Blueprint("lookups", __name__, url_prefix="/api")


@bp.get("/organizations")
@bp.get("/lookups/organizations")
@require_auth
def organizations() -> Response:
    rows = (
        db().execute(select(Organization).order_by(Organization.organization_name)).scalars().all()
    )
    return success([organization_payload(row) for row in rows])


@bp.get("/coverage-areas")
@bp.get("/lookups/coverage-areas")
@require_auth
def coverage_areas() -> Response:
    rows = db().execute(select(CoverageArea).order_by(CoverageArea.area_name)).scalars().all()
    return success(
        [
            {
                "coverage_area_id": row.coverage_area_id,
                "area_name": row.area_name,
                "city": row.city,
                "pincode": row.pincode,
            }
            for row in rows
        ]
    )


@bp.get("/food-categories")
@bp.get("/lookups/food-categories")
@require_auth
def food_categories() -> Response:
    rows = db().execute(select(FoodCategory).order_by(FoodCategory.category_name)).scalars().all()
    return success([category_payload(row) for row in rows])
