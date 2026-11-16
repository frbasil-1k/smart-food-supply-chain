"""SQLAlchemy engine/session lifecycle."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from flask import Flask, g
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .errors import ApiError


def build_engine(
    url: str | None,
    password: str | None,
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> Engine | None:
    if not url:
        return None
    parsed = make_url(url)
    if password:
        parsed = parsed.set(password=password)
    return create_engine(
        parsed,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=1800,
        pool_reset_on_return="rollback",
        echo=False,
        connect_args={
            "charset": "utf8mb4",
            "init_command": "SET time_zone = '+05:30'",
        },
    )


def init_extensions(app: Flask, settings: Settings) -> None:
    engine = build_engine(settings.database_url, settings.database_password)
    app.extensions["engine"] = engine
    app.extensions["session_factory"] = (
        sessionmaker(bind=engine, expire_on_commit=False, autoflush=False) if engine else None
    )

    @app.teardown_appcontext
    def close_session(_exception: BaseException | None) -> None:
        session: Session | None = g.pop("db_session", None)
        if session is not None:
            session.close()


def session_factory(app: Flask) -> sessionmaker[Session]:
    factory = app.extensions.get("session_factory")
    if factory is None:
        raise ApiError(500, "database_unavailable", "Database configuration is unavailable.")
    return factory


def get_session() -> Session:
    from flask import current_app

    session: Session | None = g.get("db_session")
    if session is None:
        session = session_factory(current_app)()
        g.db_session = session
    return session


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def engine_info(engine: Engine | None) -> dict[str, Any]:
    if engine is None:
        return {"configured": False}
    return {
        "configured": True,
        "dialect": engine.dialect.name,
    }
