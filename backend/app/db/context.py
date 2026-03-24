"""
Shared DB context builder for the chat assistant.

Builds a JSON-serializable dict of current Mission Control state.
"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Project, Task, AgentConfig, Note, TaskStatus,
)

MAX_TASKS = 30
MAX_NOTES = 15


async def build_db_context(db: AsyncSession) -> dict:
    """Build a complete DB context snapshot for the chat assistant."""
    context = {}

    # Projects
    result = await db.execute(select(Project).order_by(Project.name))
    context["projects"] = [
        {
            "name": p.name,
            "description": p.description[:120] if p.description else "",
            "status": p.status.value,
            "id_prefix": str(p.id)[:8],
        }
        for p in result.scalars().all()
    ]

    # Open tasks
    result = await db.execute(
        select(Task)
        .where(Task.status != TaskStatus.DONE)
        .order_by(desc(Task.created_at))
        .limit(MAX_TASKS)
    )
    context["tasks"] = [
        {
            "text": t.text,
            "status": t.status.value,
            "priority": t.priority.value,
            "id_prefix": str(t.id)[:8],
            "source": t.source or "manual",
        }
        for t in result.scalars().all()
    ]

    # Recent notes
    result = await db.execute(
        select(Note).order_by(desc(Note.updated_at)).limit(MAX_NOTES)
    )
    context["notes"] = [
        {
            "title": n.title,
            "content": n.content[:120] if n.content else "",
            "tags": n.tags or [],
            "is_pinned": n.is_pinned,
        }
        for n in result.scalars().all()
    ]

    # Agents
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.name))
    context["agents"] = [
        {
            "slug": a.slug,
            "description": a.description,
            "status": a.status.value if a.status else "idle",
            "schedule": f"{a.schedule_type}:{a.schedule_value}" if a.schedule_type else "manual",
        }
        for a in result.scalars().all()
    ]

    return context
