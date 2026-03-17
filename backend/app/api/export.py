"""
Data export API for Mission Control.

Export all data or specific entity types as JSON or CSV.
"""

import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import (
    Project, Task, Idea, ReadingItem, Habit, Goal, KeyResult,
    JournalEntry, AgentConfig, AgentRun, EventLog,
)

router = APIRouter()


async def _export_tasks(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Task).order_by(Task.created_at.desc()))
    return [
        {
            "id": str(t.id), "text": t.text, "status": t.status.value,
            "priority": t.priority.value, "source": t.source,
            "tags": ",".join(t.tags or []),
            "due_date": t.due_date.isoformat() if t.due_date else "",
            "created_at": t.created_at.isoformat(),
        }
        for t in result.scalars().all()
    ]


async def _export_projects(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return [
        {
            "id": str(p.id), "name": p.name, "description": p.description,
            "status": p.status.value, "color": p.color, "url": p.url or "",
            "created_at": p.created_at.isoformat(),
        }
        for p in result.scalars().all()
    ]


async def _export_ideas(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Idea).order_by(Idea.created_at.desc()))
    return [
        {
            "id": str(i.id), "text": i.text, "source": i.source,
            "tags": ",".join(i.tags or []), "score": i.score or "",
            "created_at": i.created_at.isoformat(),
        }
        for i in result.scalars().all()
    ]


async def _export_reading(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ReadingItem).order_by(ReadingItem.created_at.desc()))
    return [
        {
            "id": str(r.id), "title": r.title, "url": r.url or "",
            "is_read": r.is_read, "notes": r.notes or "",
            "tags": ",".join(r.tags or []),
            "created_at": r.created_at.isoformat(),
        }
        for r in result.scalars().all()
    ]


async def _export_habits(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Habit).order_by(Habit.created_at.desc()))
    return [
        {
            "id": str(h.id), "name": h.name, "description": h.description,
            "frequency": h.frequency.value, "current_streak": h.current_streak,
            "best_streak": h.best_streak, "total_completions": h.total_completions,
            "is_active": h.is_active, "created_at": h.created_at.isoformat(),
        }
        for h in result.scalars().all()
    ]


async def _export_goals(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Goal).order_by(Goal.created_at.desc()))
    return [
        {
            "id": str(g.id), "title": g.title, "description": g.description,
            "status": g.status.value, "progress": g.progress,
            "tags": ",".join(g.tags or []),
            "target_date": g.target_date.isoformat() if g.target_date else "",
            "created_at": g.created_at.isoformat(),
        }
        for g in result.scalars().all()
    ]


async def _export_journal(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(JournalEntry).order_by(JournalEntry.created_at.desc()))
    return [
        {
            "id": str(j.id), "content": j.content,
            "mood": j.mood.value if j.mood else "",
            "energy": j.energy or "",
            "tags": ",".join(j.tags or []),
            "wins": "|".join(j.wins or []),
            "challenges": "|".join(j.challenges or []),
            "gratitude": "|".join(j.gratitude or []),
            "source": j.source, "created_at": j.created_at.isoformat(),
        }
        for j in result.scalars().all()
    ]


EXPORTERS = {
    "projects": _export_projects,
    "tasks": _export_tasks,
    "ideas": _export_ideas,
    "reading": _export_reading,
    "habits": _export_habits,
    "goals": _export_goals,
    "journal": _export_journal,
}


@router.get("/json")
async def export_json(
    entities: str = Query("all", description="Comma-separated: projects,tasks,ideas,reading,habits,goals,journal"),
    db: AsyncSession = Depends(get_db),
):
    """Export all or specific entity types as JSON."""
    types = set(entities.split(",")) if entities != "all" else set(EXPORTERS.keys())
    data = {}
    for entity_type in types:
        if entity_type in EXPORTERS:
            data[entity_type] = await EXPORTERS[entity_type](db)

    data["exported_at"] = datetime.now(timezone.utc).isoformat()
    data["version"] = "0.2"

    return data


@router.get("/csv/{entity_type}")
async def export_csv(entity_type: str, db: AsyncSession = Depends(get_db)):
    """Export a specific entity type as CSV."""
    if entity_type not in EXPORTERS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}. Available: {', '.join(EXPORTERS.keys())}")

    rows = await EXPORTERS[entity_type](db)
    if not rows:
        return StreamingResponse(
            io.StringIO(""),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={entity_type}.csv"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={entity_type}_{datetime.now().strftime('%Y%m%d')}.csv"},
    )
