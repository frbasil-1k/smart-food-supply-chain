"""Opaque token generation, hashing and CSRF signing helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

TOKEN_BYTES = 32
PREAUTH_MAX_AGE_SECONDS = 2 * 60 * 60


def new_opaque_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def session_csrf_token(secret: str, sid: str, csrf_id: str) -> str:
    payload = f"{sid}.{csrf_id}"
    return f"{payload}.{sign(secret, 'csrf.' + payload)}"


def verify_session_csrf_token(secret: str, token: str, sid: str) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False
    payload = f"{parts[0]}.{parts[1]}"
    if parts[0] != sid or not parts[1]:
        return False
    expected = sign(secret, "csrf." + payload)
    return hmac.compare_digest(parts[2], expected)


def preauth_csrf_token(secret: str) -> str:
    nonce = secrets.token_urlsafe(18)
    issued = str(int(time.time()))
    payload = f"pre.{issued}.{nonce}"
    return f"{payload}.{sign(secret, 'preauth.' + payload)}"


def verify_preauth_csrf_token(secret: str, token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "pre":
        return False
    try:
        issued = int(parts[1])
    except ValueError:
        return False
    if abs(int(time.time()) - issued) > PREAUTH_MAX_AGE_SECONDS:
        return False
    payload = ".".join(parts[:3])
    expected = sign(secret, "preauth." + payload)
    return hmac.compare_digest(parts[3], expected)


def csrf_cookie_value(secret: str, sid: str, csrf_id: str) -> str:
    return session_csrf_token(secret, sid, csrf_id)


def new_sid() -> str:
    return secrets.token_urlsafe(18)


def random_epoch() -> str:
    return secrets.token_urlsafe(12)


def decode_b64(value: str) -> bytes:
    return _unb64(value)
