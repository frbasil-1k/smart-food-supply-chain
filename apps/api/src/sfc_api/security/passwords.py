"""Password hashing and the API's conservative password policy."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import ApiError

SCRYPT_METHOD = "scrypt:32768:8:1"
_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    if not _COMMON_PASSWORDS_FILE.is_file():
        return frozenset()
    return frozenset(
        line.strip().casefold()
        for line in _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=SCRYPT_METHOD)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        return False


@lru_cache(maxsize=2)
def dummy_hash() -> str:
    """A real scrypt hash used to equalise the timing of unknown-account logins."""
    return hash_password("not-a-real-password-for-timing-only")


def validate_password_strength(password: str, *, email: str, full_name: str = "") -> None:
    problems: list[dict[str, str]] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append({"field": "password", "issue": "too_short"})
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append({"field": "password", "issue": "too_long"})
    if password.casefold() in common_passwords():
        problems.append({"field": "password", "issue": "common_password"})
    local_part = email.split("@", 1)[0].strip().casefold()
    if local_part and local_part == password.casefold():
        problems.append({"field": "password", "issue": "contains_email"})
    if full_name:
        compact_name = "".join(full_name.split()).casefold()
        if compact_name and compact_name == password.casefold():
            problems.append({"field": "password", "issue": "contains_name"})
    if problems:
        raise ApiError(
            422,
            "password_policy",
            "Choose a stronger password.",
            details=problems,
        )
