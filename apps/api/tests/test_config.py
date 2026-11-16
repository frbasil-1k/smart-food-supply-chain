from __future__ import annotations

import pytest

from sfc_api import create_app
from sfc_api.config import ConfigError, Settings


def test_testing_environment_generates_an_ephemeral_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SFC_ENV", "testing")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings = Settings.from_env()

    assert settings.testing is True
    assert len(settings.secret_key) >= 32
    assert settings.timezone == "Asia/Kolkata"
    assert settings.log_level == "INFO"
    assert settings.database_url is None


def test_development_configuration_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "dev-secret-" + "y" * 40
    monkeypatch.setenv("SFC_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", secret)
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Kolkata")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://sfc_app:placeholder@127.0.0.1:3306/smart_food_supply_chain_dev",
    )

    settings = Settings.from_env()
    app = create_app(settings)

    assert settings.testing is False
    assert settings.log_level == "WARNING"
    assert app.config["SECRET_KEY"] == secret
    assert app.config["SFC_ENV"] == "development"
    assert app.config["TESTING"] is False
    assert app.extensions["sfc_settings"] is settings


def test_development_requires_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFC_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ConfigError, match="SECRET_KEY"):
        Settings.from_env()


def test_short_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFC_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "too-short")

    with pytest.raises(ConfigError, match="at least 32"):
        Settings.from_env()


@pytest.mark.parametrize("timezone", ["Not/AZone"])
def test_invalid_timezone_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    timezone: str,
) -> None:
    monkeypatch.setenv("SFC_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-" + "z" * 40)
    monkeypatch.setenv("APP_TIMEZONE", timezone)

    with pytest.raises(ConfigError, match="APP_TIMEZONE"):
        Settings.from_env()


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFC_ENV", "staging")

    with pytest.raises(ConfigError, match="SFC_ENV"):
        Settings.from_env()


def test_non_mysql_database_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFC_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-" + "z" * 40)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///local.db")

    with pytest.raises(ConfigError, match="MySQL"):
        Settings.from_env()
