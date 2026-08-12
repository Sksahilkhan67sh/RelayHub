"""
Cross-dialect time bucketing for "deliveries/hour", "events/day", etc.

Postgres has date_trunc() natively. SQLite (used in tests) doesn't, so this falls
back to strftime() with a format string that achieves the same bucketing. Both
branches are exercised by the test suite (SQLite via pytest; Postgres is the
production path, structurally identical query shape).
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, func
from sqlalchemy.ext.asyncio import AsyncSession

_SQLITE_STRFTIME_FORMATS = {
    "hour": "%Y-%m-%d %H:00:00",
    "day": "%Y-%m-%d 00:00:00",
}


def truncate_timestamp(column: ColumnElement, *, granularity: str, dialect_name: str) -> ColumnElement:
    if granularity not in ("hour", "day"):
        raise ValueError(f"Unsupported granularity '{granularity}', expected 'hour' or 'day'")

    if dialect_name == "postgresql":
        return func.date_trunc(granularity, column)

    # SQLite (and as a generic fallback)
    return func.strftime(_SQLITE_STRFTIME_FORMATS[granularity], column)


def dialect_name_for(db: AsyncSession) -> str:
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else "sqlite"
