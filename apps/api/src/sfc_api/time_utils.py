"""Local-time helpers.

API timestamps are always timezone-aware values for APP_TIMEZONE. The module
never uses ``datetime.utcnow()`` because it returns naive values.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def now_local(timezone: str) -> datetime:
    """Return the current time in ``timezone`` with second precision."""
    return datetime.now(ZoneInfo(timezone)).replace(microsecond=0)


def format_local(value: datetime) -> str:
    """Serialize an aware datetime as an offset-bearing ISO 8601 string."""
    if value.tzinfo is None:
        raise ValueError("Local API timestamps must be timezone-aware.")
    return value.isoformat()
