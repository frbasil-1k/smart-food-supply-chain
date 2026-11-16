"""Liveness endpoint.

Stage A intentionally does not touch MySQL: a database readiness probe belongs
to the integration stage, where it can be tested against the isolated API test
database.
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app

from ..config import Settings
from ..responses import success
from ..time_utils import format_local, now_local
from ..version import VERSION

bp = Blueprint("health", __name__)


@bp.get("/health")
def health() -> Response:
    settings: Settings = current_app.extensions["sfc_settings"]
    checked_at = now_local(settings.timezone)
    return success(
        {
            "status": "ok",
            "service": "sfc-api",
            "version": VERSION,
            "environment": settings.environment,
            "timezone": settings.timezone,
            "time": format_local(checked_at),
        }
    )
