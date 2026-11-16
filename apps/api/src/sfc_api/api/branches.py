"""Branch read access and manager-owned branch maintenance."""

from __future__ import annotations

from flask import Blueprint, Response, request
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from ..auth.middleware import require_auth, require_roles
from ..errors import ApiError
from ..models import Branch, Organization
from ..responses import success
from ..schemas.requests import BranchCreate, BranchPatch
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.scope import managed_branch
from ..services.serializers import branch_payload
from .helpers import actor, db, filter_value, page, paged_response

bp = Blueprint("branches", __name__, url_prefix="/api/branches")


@bp.get("")
@require_auth
def list_branches() -> Response:
    stmt = select(Branch).options(
        joinedload(Branch.organization), joinedload(Branch.regional_manager)
    )
    q = filter_value("q")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Branch.branch_name.like(like), Branch.pincode.like(like)))
    org_id = request.args.get("organization_id")
    if org_id:
        try:
            stmt = stmt.where(Branch.organization_id == int(org_id))
        except ValueError as exc:
            raise ApiError(422, "validation_error", "organization_id must be an integer.") from exc
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {"branch_name": Branch.branch_name, "branch_id": Branch.branch_id},
        [Branch.branch_name.asc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db(), stmt, page_number, page_size)
    return paged_response([branch_payload(row[0]) for row in rows], page_number, page_size, total)


@bp.get("/<int:branch_id>")
@require_auth
def branch_detail(branch_id: int) -> Response:
    branch = (
        db()
        .execute(
            select(Branch)
            .options(joinedload(Branch.organization), joinedload(Branch.regional_manager))
            .where(Branch.branch_id == branch_id)
        )
        .scalar_one_or_none()
    )
    if branch is None:
        raise ApiError(404, "not_found", "The requested branch was not found.")
    return success(branch_payload(branch))


@bp.post("")
@require_roles("NGO_MANAGER")
def create_branch() -> Response:
    payload = parse_model(BranchCreate, request.get_json(silent=True))
    db_session = db()
    if db_session.get(Organization, payload.organization_id) is None:
        raise ApiError(422, "invalid_reference", "The organization does not exist.")
    branch = Branch(
        organization_id=payload.organization_id,
        branch_name=payload.branch_name,
        address=payload.address,
        pincode=payload.pincode,
        contact_no=payload.contact_no,
        established_date=payload.established_date,
        regional_manager_user_id=actor().user_id,
    )
    db_session.add(branch)
    atomic(db_session)
    return success(branch_payload(branch), status=201)


@bp.patch("/<int:branch_id>")
@require_roles("NGO_MANAGER")
def patch_branch(branch_id: int) -> Response:
    db_session = db()
    branch = managed_branch(db_session, actor(), branch_id)
    payload = parse_model(BranchPatch, request.get_json(silent=True))
    for field in ("branch_name", "address", "pincode", "contact_no"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is None:
                raise ApiError(422, "validation_error", f"{field} cannot be null.")
            setattr(branch, field, value)
    atomic(db_session)
    return success(branch_payload(branch))
