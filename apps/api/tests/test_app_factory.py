from __future__ import annotations

from flask import Flask

from sfc_api import __version__, create_app


def test_factory_creates_an_app_without_touching_a_database(app: Flask) -> None:
    assert app.name == "sfc_api"
    assert app.config["TESTING"] is True
    assert app.config["SFC_ENV"] == "testing"
    assert app.config["PROPAGATE_EXCEPTIONS"] is False
    assert app.extensions["sfc_settings"].database_url is None
    assert __version__ == "0.1.0"


def test_health_blueprint_is_registered(app: Flask) -> None:
    assert "health.health" in app.view_functions
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/health" in rules


def test_factory_is_usable_with_environment_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SFC_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "factory-test-" + "q" * 40)

    app = create_app()

    assert app.config["TESTING"] is True
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
