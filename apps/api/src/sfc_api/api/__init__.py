"""HTTP blueprint registration."""

from __future__ import annotations

from flask import Flask

from . import (
    auth,
    branches,
    deliveries,
    dependents,
    donations,
    health,
    inspections,
    lookups,
    reports,
    routes,
    spoilage,
    users,
)


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health.bp, url_prefix="/api")
    for blueprint in (
        auth.bp,
        users.bp,
        donations.bp,
        inspections.bp,
        deliveries.bp,
        spoilage.bp,
        branches.bp,
        routes.bp,
        routes.assignments_bp,
        lookups.bp,
        dependents.bp,
        reports.bp,
    ):
        app.register_blueprint(blueprint)
