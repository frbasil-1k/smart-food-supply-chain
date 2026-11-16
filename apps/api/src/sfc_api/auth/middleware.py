"""Per-request session loading, CSRF/origin enforcement and role guards."""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask import Flask, Response, g, request
from sqlalchemy import select

from ..config import Settings
from ..errors import ApiError
from ..extensions import get_session
from ..models import AppUser, UserCredential
from .session import (
    SessionData,
    cookie_names,
    decode_session,
    require_allowed_origin,
    set_session_cookies,
    touch_session,
    validate_csrf,
)

PREAUTH_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/activate",
        "/api/auth/password-reset/confirm",
    }
)
REFRESH_INTERVAL_SECONDS = 5 * 60


def _load_user(settings: Settings, data: SessionData) -> tuple[AppUser, UserCredential] | None:
    db = get_session()
    row = db.execute(
        select(AppUser, UserCredential)
        .join(UserCredential, UserCredential.user_id == AppUser.user_id)
        .where(AppUser.user_id == data.uid)
    ).first()
    if row is None:
        return None
    user, credential = row
    if user.account_status != "ACTIVE":
        return None
    if credential.password_changed_at.isoformat(timespec="seconds") != data.epoch:
        return None
    return user, credential


def register_auth(app: Flask, settings: Settings) -> None:
    session_cookie, _ = cookie_names(settings)

    @app.before_request
    def authenticate_request() -> None:
        g.current_user = None
        g.current_credential = None
        g.session_data = None
        raw = request.cookies.get(session_cookie)
        data = decode_session(settings, raw) if raw else None
        if data is not None:
            loaded = _load_user(settings, data)
            if loaded is None:
                g.clear_session = True
            else:
                user, credential = loaded
                g.current_user = user
                g.current_credential = credential
                g.session_data = data
                g.user_id = user.user_id
                if int(time.time()) - data.seen >= REFRESH_INTERVAL_SECONDS:
                    g.refreshed_session = touch_session(data)
        elif raw:
            g.clear_session = True

    @app.before_request
    def enforce_origin_and_csrf() -> None:
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return
        # A missing route (including 405 probes) and liveness must keep their
        # framework semantics instead of becoming a CSRF rejection.
        if request.endpoint is None or request.endpoint == "health.health":
            return
        current_session: SessionData | None = g.get("session_data")
        if current_session is None and request.path not in PREAUTH_PATHS:
            # Let the role guard answer 401 rather than masking it as CSRF.
            return
        require_allowed_origin(request, settings)
        if current_session is not None:
            validate_csrf(request, settings, current_session)
        else:
            validate_csrf(request, settings, None)

    @app.after_request
    def finish_auth(response: Response) -> Response:
        if g.get("clear_session"):
            from .session import clear_session_cookies

            clear_session_cookies(response, settings)
        refreshed = g.get("refreshed_session")
        if isinstance(refreshed, SessionData):
            set_session_cookies(response, settings, refreshed)
        return response


def current_user() -> AppUser:
    user = g.get("current_user")
    if user is None:
        raise ApiError(401, "unauthenticated", "Authentication is required.")
    return cast(AppUser, user)


def require_roles[F: Callable[..., Any]](*roles: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = current_user()
            if user.user_role not in roles:
                raise ApiError(403, "forbidden_role", "Your role is not permitted to do this.")
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def require_auth[F: Callable[..., Any]](func: F) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        current_user()
        return func(*args, **kwargs)

    return cast(F, wrapper)
