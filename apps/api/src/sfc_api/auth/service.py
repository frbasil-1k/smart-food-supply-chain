"""Authentication, activation, reset and password-change use cases."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import ApiError
from ..models import AppUser, UserCredential
from ..security.passwords import (
    dummy_hash,
    hash_password,
    validate_password_strength,
    verify_password,
)
from ..security.tokens import token_hash
from ..services.common import atomic

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 10
_attempts: dict[str, list[float]] = {}
_attempts_lock = threading.Lock()


def _now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)


def _rate_key(ip: str, email: str) -> str:
    return f"{ip}|{email.casefold()}"


def check_login_rate(ip: str, email: str) -> None:
    key = _rate_key(ip, email)
    now = time.monotonic()
    with _attempts_lock:
        recent = [stamp for stamp in _attempts.get(key, []) if now - stamp < LOGIN_WINDOW_SECONDS]
        if len(recent) >= LOGIN_MAX_ATTEMPTS:
            _attempts[key] = recent
            raise ApiError(429, "rate_limited", "Too many login attempts. Try again later.")
        recent.append(now)
        _attempts[key] = recent


def clear_login_rate(ip: str, email: str) -> None:
    with _attempts_lock:
        _attempts.pop(_rate_key(ip, email), None)


def _credential_query(email: str) -> Select[tuple[AppUser, UserCredential]]:
    return (
        select(AppUser, UserCredential)
        .join(UserCredential, UserCredential.user_id == AppUser.user_id)
        .where(func.lower(AppUser.email) == email.casefold())
    )


def authenticate(
    db: Session, settings: Settings, email: str, password: str, ip: str
) -> tuple[AppUser, UserCredential]:
    check_login_rate(ip, email)
    row = db.execute(_credential_query(email)).first()
    if row is None:
        # A real scrypt check keeps unknown-account timing close to a bad password.
        verify_password(dummy_hash(), password)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    user, credential = row
    if credential.locked_until is not None and credential.locked_until > _now(settings):
        retry_after = max(1, int((credential.locked_until - _now(settings)).total_seconds()))
        raise ApiError(
            401,
            "account_locked",
            "This account is temporarily locked.",
            details=[{"field": "retry_after_seconds", "issue": str(retry_after)}],
        )
    if not verify_password(credential.password_hash, password):
        credential.failed_attempts = int(credential.failed_attempts) + 1
        if credential.failed_attempts >= MAX_FAILED_ATTEMPTS:
            credential.locked_until = _now(settings) + timedelta(minutes=LOCKOUT_MINUTES)
        atomic(db)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if user.account_status != "ACTIVE":
        raise ApiError(403, "account_inactive", "This account is not active.")
    credential.failed_attempts = 0
    credential.locked_until = None
    credential.last_login_at = func.now()
    atomic(db)
    clear_login_rate(ip, email)
    db.refresh(credential)
    return user, credential


def redeem_token(
    db: Session,
    settings: Settings,
    *,
    token: str,
    new_password: str,
    require_activation: bool,
) -> tuple[AppUser, UserCredential]:
    digest = token_hash(token)
    row = db.execute(
        select(AppUser, UserCredential)
        .join(UserCredential, UserCredential.user_id == AppUser.user_id)
        .where(UserCredential.reset_token_hash == digest)
        .with_for_update()
    ).first()
    if row is None:
        raise ApiError(401, "token_invalid_or_expired", "The activation or reset token is invalid.")
    user, credential = row
    if credential.reset_expires_at is None or credential.reset_expires_at <= _now(settings):
        raise ApiError(
            401, "token_invalid_or_expired", "The activation or reset token has expired."
        )
    if require_activation and not credential.must_change_password:
        raise ApiError(
            401, "token_invalid_or_expired", "This activation token has already been used."
        )
    validate_password_strength(new_password, email=user.email, full_name=user.full_name)
    credential.password_hash = hash_password(new_password)
    credential.password_changed_at = func.now()
    credential.reset_token_hash = None
    credential.reset_expires_at = None
    credential.must_change_password = False
    credential.failed_attempts = 0
    credential.locked_until = None
    if require_activation:
        user.account_status = "ACTIVE"
    atomic(db)
    db.refresh(credential)
    db.refresh(user)
    return user, credential


def change_password(
    db: Session,
    *,
    user: AppUser,
    credential: UserCredential,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(credential.password_hash, current_password):
        raise ApiError(401, "invalid_credentials", "The current password is incorrect.")
    validate_password_strength(new_password, email=user.email, full_name=user.full_name)
    credential.password_hash = hash_password(new_password)
    credential.password_changed_at = func.now()
    credential.must_change_password = False
    atomic(db)


def session_epoch(credential: UserCredential) -> str:
    value = credential.password_changed_at
    if isinstance(value, str):
        return value
    return value.isoformat(timespec="seconds")
