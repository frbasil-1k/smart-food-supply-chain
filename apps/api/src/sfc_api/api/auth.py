"""Authentication, session, activation and token endpoints."""

from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, g, request

from ..auth.middleware import current_user, require_auth, require_roles
from ..auth.service import (
    authenticate,
    change_password,
    redeem_token,
    session_epoch,
)
from ..auth.session import (
    clear_session_cookies,
    new_session_data,
    session_csrf_token,
    set_preauth_cookie,
    set_session_cookies,
)
from ..config import Settings
from ..extensions import get_session
from ..responses import JSON_CONTENT_TYPE, success
from ..schemas.requests import (
    ActivateRequest,
    LoginRequest,
    PasswordChangeRequest,
    ResetConfirmRequest,
)
from ..security.tokens import new_sid, random_epoch
from ..services.accounts import issue_activation, issue_reset
from ..services.common import parse_model
from ..services.serializers import user_payload

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _settings() -> Settings:
    return current_app.extensions["sfc_settings"]


def _with_token(body: dict[str, object], token: str) -> Response:
    envelope = {"data": {**body, "csrf_token": token}, "meta": {}}
    response = Response(
        json.dumps(envelope, ensure_ascii=False),
        content_type=JSON_CONTENT_TYPE,
    )
    return response


@bp.get("/csrf")
def csrf_token() -> Response:
    settings = _settings()
    data = g.get("session_data")
    response = success({})
    if data is not None:
        token = session_csrf_token(settings.secret_key, data.sid, data.csrf_id)
        response.set_data(json.dumps({"data": {"csrf_token": token}, "meta": {}}))
        response.content_type = JSON_CONTENT_TYPE
        return response
    token = set_preauth_cookie(response, settings)
    response.set_data(json.dumps({"data": {"csrf_token": token}, "meta": {}}))
    response.content_type = JSON_CONTENT_TYPE
    return response


@bp.post("/login")
def login() -> Response:
    settings = _settings()
    payload = parse_model(LoginRequest, request.get_json(silent=True))
    db = get_session()
    ip = request.remote_addr or "unknown"
    user, credential = authenticate(db, settings, payload.email, payload.password, ip)
    data = new_session_data(
        uid=user.user_id,
        epoch=session_epoch(credential),
        sid=new_sid(),
        csrf_id=random_epoch(),
    )
    token = session_csrf_token(settings.secret_key, data.sid, data.csrf_id)
    response = _with_token({"user": user_payload(user, credential=credential)}, token)
    set_session_cookies(response, settings, data)
    return response


@bp.post("/logout")
@require_auth
def logout() -> Response:
    settings = _settings()
    response = Response(status=204)
    clear_session_cookies(response, settings)
    return response


@bp.get("/me")
@require_auth
def me() -> Response:
    user = current_user()
    credential = g.get("current_credential")
    return success(user_payload(user, credential=credential))


@bp.post("/activate")
def activate() -> Response:
    settings = _settings()
    payload = parse_model(ActivateRequest, request.get_json(silent=True))
    db = get_session()
    user, credential = redeem_token(
        db,
        settings,
        token=payload.token,
        new_password=payload.new_password,
        require_activation=True,
    )
    data = new_session_data(
        uid=user.user_id,
        epoch=session_epoch(credential),
        sid=new_sid(),
        csrf_id=random_epoch(),
    )
    token = session_csrf_token(settings.secret_key, data.sid, data.csrf_id)
    response = _with_token({"user": user_payload(user, credential=credential)}, token)
    set_session_cookies(response, settings, data)
    return response


@bp.post("/password-reset/confirm")
def reset_confirm() -> Response:
    settings = _settings()
    payload = parse_model(ResetConfirmRequest, request.get_json(silent=True))
    db = get_session()
    redeem_token(
        db,
        settings,
        token=payload.token,
        new_password=payload.new_password,
        require_activation=False,
    )
    return Response(status=204)


@bp.post("/password/change")
@require_auth
def password_change() -> Response:
    settings = _settings()
    payload = parse_model(PasswordChangeRequest, request.get_json(silent=True))
    user = current_user()
    credential = g.get("current_credential")
    change_password(
        get_session(),
        user=user,
        credential=credential,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    response = Response(status=204)
    clear_session_cookies(response, settings)
    return response


@bp.post("/users/<int:user_id>/activation-token")
@require_roles("NGO_MANAGER")
def activation_token(user_id: int) -> Response:
    settings = _settings()
    token = issue_activation(get_session(), settings, current_user(), user_id)
    return success({"token": token}, status=201)


@bp.post("/users/<int:user_id>/reset-token")
@require_roles("NGO_MANAGER")
def reset_token(user_id: int) -> Response:
    settings = _settings()
    token = issue_reset(get_session(), settings, current_user(), user_id)
    return success({"token": token}, status=201)


@bp.post("/password")
@require_auth
def password_change_alias() -> Response:
    return password_change()
