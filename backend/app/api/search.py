"""Search across Mission Control entities."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Task, Project, Note, MarketingSignal, MarketingContent

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_types: str = Query("all", description="Comma-separated: tasks,notes,projects,signals,content"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query_lower = f"%{q.lower()}%"
    types = set(entity_types.split(",")) if entity_types != "all" else {
        "tasks", "notes", "projects", "signals", "content"
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

    if "notes" in types:
        stmt = select(Note).where(
            or_(func.lower(Note.title).like(query_lower),
                func.lower(Note.content).like(query_lower))
        ).order_by(Note.updated_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "note", "id": str(n.id), "title": n.title,
             "tags": n.tags or [], "created_at": n.created_at.isoformat()}
            for n in rows
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

    if "signals" in types:
        stmt = select(MarketingSignal).where(
            or_(func.lower(MarketingSignal.title).like(query_lower),
                func.lower(MarketingSignal.body).like(query_lower))
        ).order_by(MarketingSignal.created_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "signal", "id": str(s.id), "title": s.title,
             "status": s.status.value, "source_type": s.source_type,
             "created_at": s.created_at.isoformat()}
            for s in rows
        ])

    if "content" in types:
        stmt = select(MarketingContent).where(
            or_(func.lower(MarketingContent.title).like(query_lower),
                func.lower(MarketingContent.body).like(query_lower))
        ).order_by(MarketingContent.created_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        results.extend([
            {"type": "content", "id": str(c.id), "title": c.title,
             "status": c.status.value, "channel": c.channel,
             "created_at": c.created_at.isoformat()}
            for c in rows
        ])

    return {
        "query": q,
        "total": len(results),
        "results": results[:limit],
    }
