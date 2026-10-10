"""
Nightly database backups.

SQLite: a consistent copy via SQLite's backup API. PostgreSQL: `pg_dump`
(custom format; restore with `pg_restore`). Backups land in BACKUP_DIR and the
newest BACKUP_KEEP are kept. The scheduler runs this once a day at
BACKUP_HOUR in NOTIFICATION_TIMEZONE; run it by hand with:

    python -m app.db.backup
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from app.config import settings

logger = logging.getLogger(__name__)

PREFIX = "mission-control-"


def _backup_sqlite(target: Path) -> Path:
    path = target.with_suffix(".db")
    src = sqlite3.connect(settings.sqlite_path)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return path


async def _backup_postgres(target: Path) -> Path:
    path = target.with_suffix(".dump")
    url = urlparse(settings.database_url.replace("+asyncpg", ""))
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    proc = await asyncio.create_subprocess_exec(
        "pg_dump", "--format=custom", "--no-owner",
        "-h", url.hostname or "localhost", "-p", str(url.port or 5432),
        "-U", url.username or "postgres", "-f", str(path), url.path.lstrip("/"),
        env=env, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed: {stderr.decode().strip()[:300]}")
    return path


def _prune(directory: Path, keep: int) -> list[Path]:
    backups = sorted(p for p in directory.glob(f"{PREFIX}*") if p.is_file())
    removed = backups[:-keep] if keep > 0 else []
    for p in removed:
        p.unlink()
    return removed


async def run_backup() -> Path:
    directory = Path(settings.backup_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo(settings.notification_timezone)).strftime("%Y%m%d-%H%M%S")
    target = directory / f"{PREFIX}{stamp}"
    path = await asyncio.to_thread(_backup_sqlite, target) if settings.is_sqlite else await _backup_postgres(target)
    _prune(directory, settings.backup_keep)
    logger.info(f"Database backup written to {path} ({path.stat().st_size // 1024} KB)")
    return path


def last_backup_day() -> str:
    """Date ("YYYY-MM-DD") of the newest backup on disk, or "" if there is none."""
    backups = sorted(Path(settings.backup_dir).glob(f"{PREFIX}*"))
    if not backups:
        return ""
    stamp = backups[-1].name.removeprefix(PREFIX)[:8]
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def backup_due(now: datetime, last_backup_day: str | None) -> bool:
    """True once per day, at or after BACKUP_HOUR local time."""
    local = now.astimezone(ZoneInfo(settings.notification_timezone))
    return local.hour >= settings.backup_hour and local.strftime("%Y-%m-%d") != last_backup_day


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run_backup()))
