"""Account provisioning and manager-scoped activation/reset token issuance."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import ApiError
from ..models import AppUser, UserCredential
from ..security.passwords import hash_password
from ..security.tokens import new_opaque_token, token_hash
from .common import atomic
from .scope import managed_branch_ids

ACTIVATION_HOURS = 24
RESET_HOURS = 1


def _now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)


def _manager_target(
    db: Session, manager: AppUser, target_id: int
) -> tuple[AppUser, UserCredential]:
    branch_ids = managed_branch_ids(db, manager.user_id)
    row = db.execute(
        select(AppUser, UserCredential)
        .join(UserCredential, UserCredential.user_id == AppUser.user_id)
        .where(AppUser.user_id == target_id)
        .with_for_update()
    ).first()
    if row is None:
        raise ApiError(404, "not_found", "The requested user was not found.")
    target, credential = row
    if target.user_role == "NGO_MANAGER":
        raise ApiError(403, "forbidden", "Managers cannot issue tokens for another manager.")
    if target.primary_branch_id is None or target.primary_branch_id not in branch_ids:
        # Outside the manager's scope is deliberately indistinguishable from absence.
        raise ApiError(404, "not_found", "The requested user was not found.")
    return target, credential


def issue_activation(db: Session, settings: Settings, manager: AppUser, target_id: int) -> str:
    target, credential = _manager_target(db, manager, target_id)
    if target.account_status != "INACTIVE" and not credential.must_change_password:
        raise ApiError(409, "invalid_state", "This user is already active; issue a reset instead.")
    token = new_opaque_token()
    credential.reset_token_hash = token_hash(token)
    credential.reset_expires_at = _now(settings) + timedelta(hours=ACTIVATION_HOURS)
    credential.must_change_password = True
    atomic(db)
    return token


def issue_reset(db: Session, settings: Settings, manager: AppUser, target_id: int) -> str:
    _, credential = _manager_target(db, manager, target_id)
    token = new_opaque_token()
    credential.reset_token_hash = token_hash(token)
    credential.reset_expires_at = _now(settings) + timedelta(hours=RESET_HOURS)
    atomic(db)
    return token


def provision_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    role: str,
    branch_id: int | None,
    supervisor_user_id: int | None,
) -> tuple[AppUser, str]:
    """Operator-only provisioning. The returned token is shown once, never logged."""
    if role not in {"DONOR", "NGO_MANAGER", "DRIVER", "SAFETY_INSPECTOR"}:
        raise ApiError(422, "validation_error", "Unknown role.")
    existing = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email.casefold()))
    if existing is not None:
        raise ApiError(409, "duplicate_resource", "A user with that email already exists.")
    user = AppUser(
        full_name=full_name,
        email=email.lower(),
        phone=phone,
        user_role=role,
        account_status="INACTIVE",
        primary_branch_id=branch_id,
        supervisor_user_id=supervisor_user_id,
    )
    db.add(user)
    db.flush()
    token = new_opaque_token()
    db.add(
        UserCredential(
            user_id=user.user_id,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            must_change_password=True,
            failed_attempts=0,
            password_changed_at=func.now(),
            reset_token_hash=token_hash(token),
            reset_expires_at=datetime.now() + timedelta(hours=ACTIVATION_HOURS),
            created_at=func.now(),
            updated_at=func.now(),
        )
    )
    atomic(db)
    db.refresh(user)
    return user, token
