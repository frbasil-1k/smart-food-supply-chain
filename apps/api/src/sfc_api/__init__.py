"""Application factory for the Smart Food Supply Chain API."""

from __future__ import annotations

from flask import Flask
from flask.json.provider import DefaultJSONProvider

from .api import register_blueprints
from .auth.middleware import register_auth
from .cli import register_cli
from .config import Settings
from .errors import register_error_handlers
from .extensions import init_extensions
from .logging_config import configure_logging, register_request_logging
from .version import VERSION

__all__ = ["__version__", "create_app"]
__version__ = VERSION


def create_app(settings: Settings | None = None) -> Flask:
    """Build an application without connecting to any external service."""
    resolved = settings or Settings.from_env()

    app = Flask(__name__)
    app.config.from_mapping(resolved.to_flask_config())
    # Always return the contract envelope, including under pytest.
    app.config["PROPAGATE_EXCEPTIONS"] = False
    if isinstance(app.json, DefaultJSONProvider):
        app.json.ensure_ascii = False
        app.json.sort_keys = False
    app.extensions["sfc_settings"] = resolved

    configure_logging(app, resolved)
    init_extensions(app, resolved)
    register_error_handlers(app)
    register_request_logging(app)
    register_auth(app, resolved)
    register_blueprints(app)
    register_cli(app)

    return app
