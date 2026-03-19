"""Database Backup & Restore API.

Provides JSON-based backup and restore of all Mission Control data.
Also usable as CLI: python -m app.api.backup [backup|restore] [file]
"""

import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import (
    Project, Task, Idea, Note, AgentConfig, AgentMemory,
    Routine, RoutineItem, RoutineCompletion,
    EventLog, Notification,
)
from app.api.api_keys import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

# Tables to back up, in dependency order
BACKUP_TABLES = [
    ("projects", Project),
    ("tasks", Task),
    ("ideas", Idea),
    ("notes", Note),
    ("routines", Routine),
    ("routine_items", RoutineItem),
    ("routine_completions", RoutineCompletion),
    ("agent_memories", AgentMemory),
]


def _serialize_row(row) -> dict:
    """Convert a SQLAlchemy model instance to a JSON-safe dict."""
    data = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if val is None:
            data[col.name] = None
        elif hasattr(val, 'isoformat'):
            data[col.name] = val.isoformat()
        elif hasattr(val, 'value'):  # enum
            data[col.name] = val.value
        elif isinstance(val, (list, dict)):
            data[col.name] = val
        else:
            data[col.name] = str(val)
    return data


@router.get("/backup", dependencies=[Depends(require_admin)])
async def create_backup(db: AsyncSession = Depends(get_db)):
    """Create a full JSON backup of all user data."""
    backup = {
        "version": "0.4",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }

    for table_name, model in BACKUP_TABLES:
        result = await db.execute(select(model))
        rows = result.scalars().all()
        backup["tables"][table_name] = [_serialize_row(r) for r in rows]

    # Summary
    backup["summary"] = {
        table_name: len(backup["tables"][table_name])
        for table_name in backup["tables"]
    }

    return JSONResponse(content=backup)


@router.post("/restore", dependencies=[Depends(require_admin)])
async def restore_backup(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Restore data from a JSON backup file.

    WARNING: This will add data to existing tables (not replace).
    Duplicate primary keys will be skipped.
    """
    try:
        content = await file.read()
        backup = json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid backup file: {e}")

    if "tables" not in backup:
        raise HTTPException(status_code=400, detail="Invalid backup format: missing 'tables' key")

    restored = {}
    skipped = {}
    errors: list[str] = []

    for table_name, model in BACKUP_TABLES:
        rows = backup["tables"].get(table_name, [])
        count = 0
        skip = 0
        for row_data in rows:
            try:
                if not isinstance(row_data, dict):
                    skip += 1
                    errors.append(f"{table_name}: row is not a dict")
                    continue

                # Check if row already exists
                pk_col = model.__table__.primary_key.columns.values()[0]
                pk_val = row_data.get(pk_col.name)
                if pk_val:
                    from uuid import UUID as PyUUID
                    try:
                        pk_uuid = PyUUID(pk_val)
                    except (ValueError, AttributeError):
                        skip += 1
                        errors.append(f"{table_name}: invalid UUID '{pk_val}'")
                        continue
                    existing = await db.get(model, pk_uuid)
                    if existing:
                        skip += 1
                        continue

                # Create new row (skip relationship fields)
                col_names = {c.name for c in model.__table__.columns}
                filtered = {k: v for k, v in row_data.items() if k in col_names}
                obj = model(**filtered)
                db.add(obj)
                count += 1
            except Exception as e:
                skip += 1
                errors.append(f"{table_name}: {e}")
                logger.warning(f"Skipped row in {table_name}: {e}")

        restored[table_name] = count
        skipped[table_name] = skip

    try:
        await db.flush()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")

    return {
        "restored": restored,
        "skipped": skipped,
        "errors": errors[:50],  # Cap error list to prevent huge responses
        "source_version": backup.get("version", "unknown"),
        "source_date": backup.get("created_at", "unknown"),
    }


@router.get("/backup/summary")
async def backup_summary(db: AsyncSession = Depends(get_db)):
    """Get a summary of what would be backed up."""
    summary = {}
    for table_name, model in BACKUP_TABLES:
        result = await db.execute(select(func.count()).select_from(model))
        summary[table_name] = result.scalar() or 0
    return {"total_rows": sum(summary.values()), "tables": summary}
