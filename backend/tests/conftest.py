"""Test configuration - mock heavy dependencies that aren't needed for API tests."""

import sys
import json
from unittest.mock import MagicMock

# Mock heavy deps that aren't needed for API tests
for mod_name in [
    "telegram", "telegram.ext", "telegram.constants",
    "discord", "discord.ext", "discord.ext.commands",
    "feedparser",
    "claude_agent_sdk",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Make PostgreSQL ARRAY and UUID types work with SQLite
import sqlalchemy as sa
from sqlalchemy import TypeDecorator, Text, String, event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.dialects.postgresql import ARRAY, UUID


# Type compilation (DDL)
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "TEXT"
SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "VARCHAR(36)"


# Value binding/result — ARRAY columns need JSON serialization for SQLite
class _ArrayAdapter(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return json.loads(value)


# Monkey-patch ARRAY to use our adapter when running on SQLite
_orig_array_adapt = ARRAY.__class_getitem__ if hasattr(ARRAY, '__class_getitem__') else None

@event.listens_for(sa.engine.Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Patch the ARRAY type to adapt for SQLite at bind time
_orig_bind_processor = ARRAY.bind_processor if hasattr(ARRAY, 'bind_processor') else None


def _array_bind_processor(self, dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return None
            return json.dumps(value)
        return process
    if _orig_bind_processor:
        return _orig_bind_processor(self, dialect)
    return None


def _array_result_processor(self, dialect, coltype):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            return json.loads(value)
        return process
    return None


ARRAY.bind_processor = _array_bind_processor
ARRAY.result_processor = _array_result_processor
