"""Manager-scoped user listing and account-status administration."""

from __future__ import annotations

from flask import Blueprint, Response, request
from sqlalchemy import or_, select

from ..auth.middleware import require_auth, require_roles
from ..errors import ApiError
from ..models import AppUser
from ..responses import success
from ..schemas.requests import AccountStatusRequest
from ..services.common import apply_sort, atomic, paginate, parse_model
from ..services.scope import managed_branch_ids
from ..services.serializers import user_payload
from .helpers import actor, db, filter_value, page, paged_response

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@require_roles("NGO_MANAGER")
def list_users() -> Response:
    user = actor()
    branch_ids = managed_branch_ids(db(), user.user_id)
    if not branch_ids:
        return paged_response([], 1, 25, 0)
    stmt = select(AppUser).where(
        AppUser.primary_branch_id.in_(branch_ids),
        AppUser.user_role != "NGO_MANAGER",
    )
    role = filter_value("role")
    if role:
        stmt = stmt.where(AppUser.user_role == role)
    status = filter_value("account_status")
    if status:
        stmt = stmt.where(AppUser.account_status == status)
    q = filter_value("q")
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(AppUser.full_name.like(pattern), AppUser.email.like(pattern)))
    stmt = apply_sort(
        stmt,
        request.args.get("sort"),
        {
            "full_name": AppUser.full_name,
            "email": AppUser.email,
            "role": AppUser.user_role,
            "account_status": AppUser.account_status,
            "user_id": AppUser.user_id,
        },
        [AppUser.full_name.asc(), AppUser.user_id.asc()],
    )
    page_number, page_size = page()
    rows, total = paginate(db(), stmt, page_number, page_size)
    payload = [user_payload(row[0], credential=row[0].credential) for row in rows]
    return paged_response(payload, page_number, page_size, total)


@bp.get("/<int:user_id>")
@require_auth
def get_user(user_id: int) -> Response:
    current = actor()
    target = db().get(AppUser, user_id)
    if target is None:
        raise ApiError(404, "not_found", "The requested user was not found.")
    if target.user_id != current.user_id:
        if (
            current.user_role != "NGO_MANAGER"
            or target.primary_branch_id not in managed_branch_ids(db(), current.user_id)
        ):
            raise ApiError(404, "not_found", "The requested user was not found.")
        if target.user_role == "NGO_MANAGER":
            raise ApiError(404, "not_found", "The requested user was not found.")
    return success(user_payload(target, credential=target.credential))


@bp.patch("/<int:user_id>")
@require_roles("NGO_MANAGER")
def update_user_status(user_id: int) -> Response:
    current = actor()
    if user_id == current.user_id:
        raise ApiError(403, "forbidden", "Managers cannot change their own account status.")
    target = db().get(AppUser, user_id)
    if (
        target is None
        or target.user_role == "NGO_MANAGER"
        or target.primary_branch_id not in managed_branch_ids(db(), current.user_id)
    ):
        raise ApiError(404, "not_found", "The requested user was not found.")
    payload = parse_model(AccountStatusRequest, request.get_json(silent=True))
    target.account_status = payload.account_status
    atomic(db())
    return success(user_payload(target, credential=target.credential))


@bp.post("/<int:user_id>/activation-token")
@require_roles("NGO_MANAGER")
def user_activation_token(user_id: int) -> Response:
    from ..services.accounts import issue_activation
    from ..services.serializers import iso_datetime

    settings = __import__("flask").current_app.extensions["sfc_settings"]
    token = issue_activation(db(), settings, actor(), user_id)
    credential = db().get(
        __import__("sfc_api.models", fromlist=["UserCredential"]).UserCredential, user_id
    )
    return success(
        {
            "activation_token": token,
            "expires_at": iso_datetime(credential.reset_expires_at if credential else None),
            "delivery": "shown_once",
        },
        status=201,
    )


@bp.post("/<int:user_id>/password-reset-token")
@require_roles("NGO_MANAGER")
def user_reset_token(user_id: int) -> Response:
    from ..services.accounts import issue_reset
    from ..services.serializers import iso_datetime

    settings = __import__("flask").current_app.extensions["sfc_settings"]
    token = issue_reset(db(), settings, actor(), user_id)
    credential = db().get(
        __import__("sfc_api.models", fromlist=["UserCredential"]).UserCredential, user_id
    )
    return success(
        {
            "reset_token": token,
            "expires_at": iso_datetime(credential.reset_expires_at if credential else None),
            "delivery": "shown_once",
        },
        status=201,
    )


@bp.get("/me/activity")
@require_auth
def my_activity() -> Response:
    # Kept here so clients can discover a stable endpoint even though the full
    # activity feed lives at /api/reports/activity.
    return success([])
