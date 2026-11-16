from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base; schema creation is intentionally never performed."""


class ViewBase(DeclarativeBase):
    """Read-only mapping base for the three approved views."""
