"""Nightly backups: SQLite copy, retention, once a day."""

import sqlite3
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.db import backup


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    db = tmp_path / "mc.db"
    con = sqlite3.connect(db)
    con.execute("create table t (x int)")
    con.execute("insert into t values (42)")
    con.commit()
    con.close()
    monkeypatch.setattr(settings, "use_sqlite", True)
    monkeypatch.setattr(settings, "sqlite_path", str(db))
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_keep", 2)
    monkeypatch.setattr(settings, "notification_timezone", "UTC")
    return tmp_path


@pytest.mark.asyncio
async def test_sqlite_backup_is_a_usable_copy(sqlite_db):
    path = await backup.run_backup()
    assert sqlite3.connect(path).execute("select x from t").fetchone() == (42,)
    assert backup.last_backup_day() == datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_old_backups_are_pruned(sqlite_db):
    old = sqlite_db / "backups"
    old.mkdir()
    for day in ("20260101", "20260102", "20260103"):
        (old / f"mission-control-{day}-030000.db").write_text("x")
    await backup.run_backup()
    assert len(list(old.glob("mission-control-*"))) == 2


def test_backup_runs_once_a_day_after_the_hour(monkeypatch):
    monkeypatch.setattr(settings, "notification_timezone", "UTC")
    monkeypatch.setattr(settings, "backup_hour", 3)
    assert not backup.backup_due(datetime(2026, 10, 10, 2, 59, tzinfo=timezone.utc), "2026-10-09")
    assert backup.backup_due(datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc), "2026-10-09")
    assert not backup.backup_due(datetime(2026, 10, 10, 23, 0, tzinfo=timezone.utc), "2026-10-10")
