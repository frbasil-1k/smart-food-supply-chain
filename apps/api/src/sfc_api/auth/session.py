"""Signed session and double-submit CSRF handling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..config import Settings
from ..errors import ApiError
from ..security.tokens import (
    preauth_csrf_token,
    session_csrf_token,
    verify_preauth_csrf_token,
    verify_session_csrf_token,
)

SESSION_SALT = "sfc.session.v1"


@dataclass(frozen=True, slots=True)
class SessionData:
    uid: int
    sid: str
    iat: int
    seen: int
    epoch: str
    csrf_id: str


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=SESSION_SALT)


def encode_session(settings: Settings, data: SessionData) -> str:
    payload: dict[str, Any] = {
        "uid": data.uid,
        "sid": data.sid,
        "iat": data.iat,
        "seen": data.seen,
        "epoch": data.epoch,
        "csrf_id": data.csrf_id,
    }
    return _serializer(settings).dumps(payload)


def decode_session(settings: Settings, value: str) -> SessionData | None:
    try:
        payload = _serializer(settings).loads(value, max_age=settings.session_absolute_seconds)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    try:
        data = SessionData(
            uid=int(payload["uid"]),
            sid=str(payload["sid"]),
            iat=int(payload["iat"]),
            seen=int(payload["seen"]),
            epoch=str(payload["epoch"]),
            csrf_id=str(payload["csrf_id"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    now = int(time.time())
    if now - data.seen > settings.session_idle_seconds:
        return None
    if now - data.iat > settings.session_absolute_seconds:
        return None
    return data


def cookie_names(settings: Settings) -> tuple[str, str]:
    if settings.cookie_secure:
        return "__Host-sfc_session", "__Host-sfc_csrf"
    return "sfc_session", "sfc_csrf"


def set_session_cookies(
    response: Response,
    settings: Settings,
    data: SessionData,
) -> str:
    session_cookie, csrf_cookie = cookie_names(settings)
    token = session_csrf_token(settings.secret_key, data.sid, data.csrf_id)
    max_age = settings.session_absolute_seconds
    response.set_cookie(
        session_cookie,
        encode_session(settings, data),
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        csrf_cookie,
        token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="Lax",
        path="/",
    )
    return token


def set_preauth_cookie(response: Response, settings: Settings) -> str:
    _, csrf_cookie = cookie_names(settings)
    token = preauth_csrf_token(settings.secret_key)
    response.set_cookie(
        csrf_cookie,
        token,
        max_age=7200,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="Lax",
        path="/",
    )
    return token


def clear_session_cookies(response: Response, settings: Settings) -> None:
    session_cookie, csrf_cookie = cookie_names(settings)
    response.delete_cookie(session_cookie, path="/")
    response.delete_cookie(csrf_cookie, path="/")


def read_csrf_token(request: Request) -> str | None:
    header = request.headers.get("X-CSRF-Token")
    if header:
        return header.strip()
    return None


def validate_csrf(request: Request, settings: Settings, session: SessionData | None) -> None:
    """Reject unsafe requests with no matching token, cookie and signed binding."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    header = read_csrf_token(request)
    _, csrf_cookie = cookie_names(settings)
    cookie = request.cookies.get(csrf_cookie)
    if not header or not cookie or header != cookie:
        raise ApiError(403, "csrf_failed", "The CSRF token is missing or invalid.")
    if session is not None:
        if not verify_session_csrf_token(settings.secret_key, header, session.sid):
            raise ApiError(403, "csrf_failed", "The CSRF token is missing or invalid.")
    elif not verify_preauth_csrf_token(settings.secret_key, header):
        raise ApiError(403, "csrf_failed", "The CSRF token is missing or invalid.")


def require_allowed_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("Origin")
    if origin:
        candidate = origin.rstrip("/")
    else:
        referer = request.headers.get("Referer")
        if not referer:
            raise ApiError(403, "origin_not_allowed", "The request origin is not allowed.")
        from urllib.parse import urlsplit

        split = urlsplit(referer)
        candidate = f"{split.scheme}://{split.netloc}"
    if candidate not in settings.app_origins:
        raise ApiError(403, "origin_not_allowed", "The request origin is not allowed.")


def new_session_data(*, uid: int, epoch: str, sid: str, csrf_id: str) -> SessionData:
    now = int(time.time())
    return SessionData(uid=uid, sid=sid, iat=now, seen=now, epoch=epoch, csrf_id=csrf_id)


def touch_session(data: SessionData) -> SessionData:
    return SessionData(
        uid=data.uid,
        sid=data.sid,
        iat=data.iat,
        seen=int(datetime.now(UTC).timestamp()),
        epoch=data.epoch,
        csrf_id=data.csrf_id,
    )
