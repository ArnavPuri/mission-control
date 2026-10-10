"""Test configuration - mock heavy dependencies that aren't needed for API tests."""

import sys
from unittest.mock import MagicMock

# Mock heavy deps that aren't needed for API tests
for mod_name in [
    "telegram", "telegram.ext", "telegram.constants",
    "claude_agent_sdk",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

import sqlalchemy as sa
from sqlalchemy import event


@event.listens_for(sa.engine.Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite (tests only use SQLite)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
