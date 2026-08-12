"""
Cross-dialect column types.

StringList uses native Postgres ARRAY(String) in production, but falls back to a
JSON-encoded TEXT column on SQLite (used only in the test suite) since SQLite has no
array type. This keeps tests running against a real, fast, in-memory DB without
needing a live Postgres for every module's test run.
"""

import json

from sqlalchemy import JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator


class StringList(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.ARRAY(String))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return [] if dialect.name != "postgresql" else None
        if dialect.name == "postgresql":
            return value
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
