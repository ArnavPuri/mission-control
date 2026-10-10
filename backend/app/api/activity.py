"""Recent activity across task threads, for the dashboard's activity feed."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentConfig, Task, TaskComment
from app.db.session import get_db

router = APIRouter()


@router.get("")
async def recent_activity(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    """Latest thread messages (agent replies, your replies, system events), newest first."""
    rows = (await db.execute(
        select(TaskComment, Task)
        .join(Task, Task.id == TaskComment.task_id)
        .order_by(TaskComment.created_at.desc())
        .limit(limit)
    )).all()
    names = {
        f"agent:{a.slug}": a.name
        for a in (await db.execute(select(AgentConfig))).scalars().all()
    }
    return [
        {
            "id": str(c.id),
            "author": c.author,
            "author_name": "You" if c.author == "user" else "System" if c.author == "system"
            else names.get(c.author, c.author.removeprefix("agent:")),
            "body": c.body[:400],
            "created_at": c.created_at.isoformat(),
            "task": {"id": str(t.id), "text": t.text, "status": t.status.value},
        }
        for c, t in rows
    ]
