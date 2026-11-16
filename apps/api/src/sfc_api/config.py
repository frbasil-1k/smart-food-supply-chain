"""Environment-driven application settings.

Secrets are read from protected files outside the repository by default. The
database URL stored on Settings never carries the password; the password lives in
a separate, non-repr field and is supplied to the engine at connect time.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.engine import URL, make_url

VALID_ENVIRONMENTS = frozenset({"development", "testing", "production"})
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
DEFAULT_TIMEZONE = "Asia/Kolkata"


class ConfigError(ValueError):
    """Raised when the environment cannot produce a safe configuration."""


def _read(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _read_file(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise ConfigError(f"Secret file does not exist: {path.name}.")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ConfigError(f"Secret file is empty: {path.name}.")
    return value


def _mysql_url(value: str) -> tuple[str, str | None]:
    """Return a password-free URL and any password embedded in the input."""
    try:
        parsed = make_url(value)
    except Exception as exc:  # SQLAlchemy raises ArgumentError for malformed URLs
        raise ConfigError("DATABASE_URL is not a valid SQLAlchemy URL.") from exc
    if parsed.drivername not in {"mysql+pymysql", "mysql"}:
        raise ConfigError("DATABASE_URL must be a MySQL SQLAlchemy URL.")
    password = parsed.password
    without_password: URL = parsed.set(password=None)
    return without_password.render_as_string(hide_password=False), password


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    secret_key: str = field(repr=False)
    timezone: str
    log_level: str
    database_url: str | None
    testing: bool
    database_password: str | None = field(default=None, repr=False)
    ops_database_url: str | None = None
    ops_database_password: str | None = field(default=None, repr=False)
    app_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    cookie_secure: bool = False
    session_idle_seconds: int = 8 * 60 * 60
    session_absolute_seconds: int = 12 * 60 * 60

    @classmethod
    def from_env(cls, environment: str | None = None) -> Settings:
        env_name = (environment or _read("SFC_ENV", "development") or "development").lower()
        if env_name not in VALID_ENVIRONMENTS:
            allowed = ", ".join(sorted(VALID_ENVIRONMENTS))
            raise ConfigError(f"SFC_ENV must be one of: {allowed}.")

        secret_key = _read("SECRET_KEY")
        if secret_key is None:
            secret_key = _read_file(_read("SECRET_KEY_FILE"))
        if secret_key is None:
            if env_name != "testing":
                raise ConfigError("SECRET_KEY or SECRET_KEY_FILE must be set.")
            secret_key = secrets.token_urlsafe(48)
        elif len(secret_key) < 32 and env_name != "testing":
            raise ConfigError("SECRET_KEY must contain at least 32 characters.")

        timezone = _read("APP_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ConfigError(f"APP_TIMEZONE is not a known IANA timezone: {timezone}.") from exc

        log_level = (_read("LOG_LEVEL", "INFO") or "INFO").upper()
        if log_level not in VALID_LOG_LEVELS:
            allowed = ", ".join(sorted(VALID_LOG_LEVELS))
            raise ConfigError(f"LOG_LEVEL must be one of: {allowed}.")

        raw_database_url = _read("DATABASE_URL")
        database_url: str | None = None
        database_password: str | None = None
        if raw_database_url:
            database_url, database_password = _mysql_url(raw_database_url)
            file_password = _read_file(_read("SFC_DB_PASSWORD_FILE"))
            if file_password:
                database_password = file_password
            if database_password is None and env_name != "testing":
                raise ConfigError("SFC_DB_PASSWORD_FILE must point at the sfc_app password file.")

        raw_ops_url = _read("SFC_OPS_DATABASE_URL")
        ops_database_url: str | None = None
        ops_database_password: str | None = None
        if raw_ops_url:
            ops_database_url, ops_database_password = _mysql_url(raw_ops_url)
            file_password = _read_file(_read("SFC_OPS_PASSWORD_FILE"))
            if file_password:
                ops_database_password = file_password

        origins = tuple(
            origin.strip().rstrip("/")
            for origin in (_read("APP_ORIGINS") or "").split(",")
            if origin.strip()
        ) or ("http://127.0.0.1:5173", "http://localhost:5173")

        secure_override = _read("SFC_COOKIE_SECURE")
        cookie_secure = (
            secure_override == "1" if secure_override is not None else env_name == "production"
        )

        return cls(
            environment=env_name,
            secret_key=secret_key,
            timezone=timezone,
            log_level=log_level,
            database_url=database_url,
            testing=env_name == "testing",
            database_password=database_password,
            ops_database_url=ops_database_url,
            ops_database_password=ops_database_password,
            app_origins=origins,
            cookie_secure=cookie_secure,
        )

    def to_flask_config(self) -> dict[str, object]:
        return {
            "SECRET_KEY": self.secret_key,
            "TESTING": self.testing,
            "SFC_ENV": self.environment,
            "APP_TIMEZONE": self.timezone,
            "LOG_LEVEL": self.log_level,
            "DATABASE_URL": self.database_url,
            "APP_ORIGINS": self.app_origins,
            "SESSION_COOKIE_SECURE": self.cookie_secure,
        }
