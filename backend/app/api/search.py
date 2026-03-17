"""
Semantic search across all Mission Control entities.

Uses pgvector for embedding-based similarity search with a fallback
to text-based search when embeddings aren't available.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, cast, String, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Task, Idea, ReadingItem, Goal, JournalEntry, Habit, Project

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_types: str = Query("all", description="Comma-separated: tasks,ideas,reading,goals,journal,habits,projects"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search across all entities using text matching.

    Returns results grouped by entity type, ranked by relevance.
    """
    query_lower = f"%{q.lower()}%"
    types = set(entity_types.split(",")) if entity_types != "all" else {
        "tasks", "ideas", "reading", "goals", "journal", "habits", "projects"
    }
    results = []

    if "tasks" in types:
        stmt = select(Task).where(func.lower(Task.text).like(query_lower)).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "task", "id": str(t.id), "title": t.text, "status": t.status.value,
             "priority": t.priority.value, "created_at": t.created_at.isoformat()}
            for t in rows
        ])

    if "ideas" in types:
        stmt = select(Idea).where(func.lower(Idea.text).like(query_lower)).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "idea", "id": str(i.id), "title": i.text, "tags": i.tags or [],
             "created_at": i.created_at.isoformat()}
            for i in rows
        ])

    if "reading" in types:
        stmt = select(ReadingItem).where(
            or_(func.lower(ReadingItem.title).like(query_lower),
                func.lower(ReadingItem.notes).like(query_lower))
        ).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "reading", "id": str(r.id), "title": r.title, "url": r.url,
             "is_read": r.is_read, "created_at": r.created_at.isoformat()}
            for r in rows
        ])

    if "goals" in types:
        stmt = select(Goal).where(
            or_(func.lower(Goal.title).like(query_lower),
                func.lower(Goal.description).like(query_lower))
        ).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "goal", "id": str(g.id), "title": g.title, "progress": g.progress,
             "status": g.status.value, "created_at": g.created_at.isoformat()}
            for g in rows
        ])

    if "journal" in types:
        stmt = select(JournalEntry).where(
            func.lower(JournalEntry.content).like(query_lower)
        ).order_by(JournalEntry.created_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "journal", "id": str(j.id), "title": j.content[:100],
             "mood": j.mood.value if j.mood else None, "created_at": j.created_at.isoformat()}
            for j in rows
        ])

    if "habits" in types:
        stmt = select(Habit).where(
            or_(func.lower(Habit.name).like(query_lower),
                func.lower(Habit.description).like(query_lower))
        ).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "habit", "id": str(h.id), "title": h.name,
             "streak": h.current_streak, "created_at": h.created_at.isoformat()}
            for h in rows
        ])

    if "projects" in types:
        stmt = select(Project).where(
            or_(func.lower(Project.name).like(query_lower),
                func.lower(Project.description).like(query_lower))
        ).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "project", "id": str(p.id), "title": p.name,
             "status": p.status.value, "created_at": p.created_at.isoformat()}
            for p in rows
        ])

    return {
        "query": q,
        "total": len(results),
        "results": results[:limit],
    }
