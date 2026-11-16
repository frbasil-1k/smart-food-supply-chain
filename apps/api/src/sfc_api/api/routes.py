"""Route maintenance and route-assignment endpoints."""

from __future__ import annotations

from flask import Blueprint, Response, request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth.middleware import require_auth, require_roles
from ..errors import ApiError
from ..models import AppUser, CoverageArea, Route, RouteAssignment
from ..responses import success
from ..schemas.requests import RouteAssignmentCreate, RouteCreate, RoutePatch
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.scope import managed_branch_ids, managed_route
from ..services.serializers import assignment_payload, route_payload
from .helpers import actor, db, filter_value, int_filter, page, paged_response

bp = Blueprint("routes", __name__, url_prefix="/api/routes")


def _driver(db_session: Session, driver_id: int) -> AppUser:
    driver = db_session.get(AppUser, driver_id)
    if driver is None or driver.user_role != "DRIVER" or driver.account_status != "ACTIVE":
        raise ApiError(422, "invalid_reference", "The designated driver is not active.")
    return driver


@bp.get("")
@require_auth
def list_routes() -> Response:
    stmt = select(Route).options(
        joinedload(Route.managing_branch),
        joinedload(Route.designated_driver),
        joinedload(Route.coverage_area),
    )
    branch_id = int_filter("branch_id")
    if branch_id:
        stmt = stmt.where(Route.managing_branch_id == branch_id)
    status = filter_value("route_status")
    if status:
        stmt = stmt.where(Route.route_status == status)
    route_type = filter_value("route_type")
    if route_type:
        stmt = stmt.where(Route.route_type == route_type)
    driver_id = int_filter("driver_id")
    if driver_id:
        stmt = stmt.where(Route.designated_driver_user_id == driver_id)
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {"route_id": Route.route_id, "route_type": Route.route_type},
        [Route.route_id.asc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db(), stmt, page_number, page_size)
    return paged_response([route_payload(row[0]) for row in rows], page_number, page_size, total)


@bp.get("/<int:route_id>")
@require_auth
def route_detail(route_id: int) -> Response:
    route = (
        db()
        .execute(
            select(Route)
            .options(
                joinedload(Route.managing_branch),
                joinedload(Route.designated_driver),
                joinedload(Route.coverage_area),
            )
            .where(Route.route_id == route_id)
        )
        .scalar_one_or_none()
    )
    if route is None:
        raise ApiError(404, "not_found", "The requested route was not found.")
    return success(route_payload(route))


@bp.post("")
@require_roles("NGO_MANAGER")
def create_route() -> Response:
    payload = parse_model(RouteCreate, request.get_json(silent=True))
    db_session = db()
    if payload.managing_branch_id not in managed_branch_ids(db_session, actor().user_id):
        raise ApiError(404, "not_found", "The managing branch was not found.")
    _driver(db_session, payload.designated_driver_user_id)
    if db_session.get(CoverageArea, payload.coverage_area_id) is None:
        raise ApiError(422, "invalid_reference", "The coverage area does not exist.")
    route = Route(
        managing_branch_id=payload.managing_branch_id,
        designated_driver_user_id=payload.designated_driver_user_id,
        coverage_area_id=payload.coverage_area_id,
        route_type=payload.route_type,
        route_status=payload.route_status,
    )
    db_session.add(route)
    atomic(db_session)
    return success(route_payload(route), status=201)


@bp.patch("/<int:route_id>")
@require_roles("NGO_MANAGER")
def patch_route(route_id: int) -> Response:
    db_session = db()
    route = managed_route(db_session, actor(), route_id)
    payload = parse_model(RoutePatch, request.get_json(silent=True))
    if (
        "designated_driver_user_id" in payload.model_fields_set
        and payload.designated_driver_user_id
    ):
        _driver(db_session, payload.designated_driver_user_id)
        route.designated_driver_user_id = payload.designated_driver_user_id
    if "coverage_area_id" in payload.model_fields_set and payload.coverage_area_id:
        if db_session.get(CoverageArea, payload.coverage_area_id) is None:
            raise ApiError(422, "invalid_reference", "The coverage area does not exist.")
        route.coverage_area_id = payload.coverage_area_id
    for field in ("route_type", "route_status"):
        if field in payload.model_fields_set and getattr(payload, field) is not None:
            setattr(route, field, getattr(payload, field))
    atomic(db_session)
    return success(route_payload(route))


@bp.get("/<int:route_id>/assignments")
@require_auth
def list_assignments(route_id: int) -> Response:
    db_session = db()
    route = db_session.get(Route, route_id)
    if route is None:
        raise ApiError(404, "not_found", "The requested route was not found.")
    user = actor()
    if user.user_role == "NGO_MANAGER":
        if route.managing_branch_id not in managed_branch_ids(db_session, user.user_id):
            raise ApiError(404, "not_found", "The requested route was not found.")
    elif user.user_role == "DRIVER":
        if (
            route.designated_driver_user_id != user.user_id
            and db_session.scalar(
                select(RouteAssignment.user_id).where(
                    RouteAssignment.route_id == route_id, RouteAssignment.user_id == user.user_id
                )
            )
            is None
        ):
            raise ApiError(404, "not_found", "The requested route was not found.")
    else:
        raise ApiError(403, "forbidden", "Your role cannot read route assignments.")
    rows = (
        db_session.execute(
            select(RouteAssignment)
            .options(joinedload(RouteAssignment.route), joinedload(RouteAssignment.user))
            .where(RouteAssignment.route_id == route_id)
            .order_by(RouteAssignment.assigned_date.asc(), RouteAssignment.user_id.asc())
        )
        .scalars()
        .all()
    )
    return success([assignment_payload(row) for row in rows])


@bp.post("/<int:route_id>/assignments")
@require_roles("NGO_MANAGER")
def create_assignment(route_id: int) -> Response:
    db_session = db()
    route = managed_route(db_session, actor(), route_id)
    payload = parse_model(RouteAssignmentCreate, request.get_json(silent=True))
    driver = db_session.get(AppUser, payload.user_id)
    if driver is None or driver.user_role != "DRIVER" or driver.account_status != "ACTIVE":
        raise ApiError(422, "invalid_reference", "The assigned user is not an active driver.")
    assignment = RouteAssignment(
        user_id=payload.user_id,
        route_id=route.route_id,
        hours_per_week=payload.hours_per_week,
        assigned_date=payload.assigned_date,
    )
    db_session.add(assignment)
    atomic(db_session)
    return success(assignment_payload(assignment), status=201)


@bp.delete("/<int:route_id>/assignments/<int:user_id>")
@require_roles("NGO_MANAGER")
def delete_assignment(route_id: int, user_id: int) -> Response:
    db_session = db()
    route = managed_route(db_session, actor(), route_id)
    assignment = db_session.get(RouteAssignment, (user_id, route.route_id))
    if assignment is None:
        raise ApiError(404, "not_found", "The requested route assignment was not found.")
    db_session.delete(assignment)
    atomic(db_session)
    return Response(status=204)


assignments_bp = Blueprint("route_assignments", __name__, url_prefix="/api/route-assignments")


@assignments_bp.get("")
@require_auth
def list_top_assignments() -> Response:
    db_session = db()
    user = actor()
    stmt = select(RouteAssignment).options(
        joinedload(RouteAssignment.route), joinedload(RouteAssignment.user)
    )
    route_id = int_filter("route_id")
    if route_id:
        stmt = stmt.where(RouteAssignment.route_id == route_id)
    user_id = int_filter("user_id")
    if user_id:
        stmt = stmt.where(RouteAssignment.user_id == user_id)
    if user.user_role == "NGO_MANAGER":
        ids = managed_branch_ids(db_session, user.user_id)
        if not ids:
            return success([])
        stmt = stmt.where(
            RouteAssignment.route_id.in_(
                select(Route.route_id).where(Route.managing_branch_id.in_(ids))
            )
        )
    elif user.user_role == "DRIVER":
        stmt = stmt.where(RouteAssignment.user_id == user.user_id)
    else:
        raise ApiError(403, "forbidden", "Your role cannot read route assignments.")
    rows = (
        db_session.execute(
            stmt.order_by(RouteAssignment.assigned_date.asc(), RouteAssignment.user_id.asc())
        )
        .scalars()
        .all()
    )
    return success([assignment_payload(row) for row in rows])


@assignments_bp.post("")
@require_roles("NGO_MANAGER")
def create_top_assignment() -> Response:
    from ..schemas.requests import TopRouteAssignmentCreate

    payload = parse_model(TopRouteAssignmentCreate, request.get_json(silent=True))
    db_session = db()
    route = managed_route(db_session, actor(), payload.route_id)
    driver = db_session.get(AppUser, payload.user_id)
    if driver is None or driver.user_role != "DRIVER" or driver.account_status != "ACTIVE":
        raise ApiError(422, "invalid_reference", "The assigned user is not an active driver.")
    assignment = RouteAssignment(
        user_id=payload.user_id,
        route_id=route.route_id,
        hours_per_week=payload.hours_per_week,
        assigned_date=payload.assigned_date,
    )
    db_session.add(assignment)
    atomic(db_session)
    return success(assignment_payload(assignment), status=201)


@assignments_bp.delete("/<int:user_id>/<int:route_id>")
@require_roles("NGO_MANAGER")
def delete_top_assignment(user_id: int, route_id: int) -> Response:
    db_session = db()
    route = managed_route(db_session, actor(), route_id)
    assignment = db_session.get(RouteAssignment, (user_id, route.route_id))
    if assignment is None:
        raise ApiError(404, "not_found", "The requested route assignment was not found.")
    db_session.delete(assignment)
    atomic(db_session)
    return Response(status=204)
