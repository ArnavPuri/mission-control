"""
Shared DB context builder for the chat assistant.

Builds a JSON-serializable dict of current Mission Control state
with size limits to keep LLM prompts reasonable.
"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Project, Task, Idea, ReadingItem, AgentConfig,
    TaskStatus, Habit, Goal, GoalStatus, JournalEntry,
)


# Size limits for chat context
MAX_TASKS = 30
MAX_IDEAS = 15
MAX_READING = 10
MAX_JOURNAL = 5


async def build_db_context(db: AsyncSession) -> dict:
    """Build a complete DB context snapshot for the chat assistant.

    Returns a dict with: projects, tasks, ideas, reading, agents.
    Each section is a list of dicts, size-limited for prompt efficiency.
    """
    context = {}

    # Projects — all (typically <10)
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

    # Open tasks — most recent
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

    # Ideas — most recent
    result = await db.execute(
        select(Idea).order_by(desc(Idea.created_at)).limit(MAX_IDEAS)
    )
    context["ideas"] = [
        {
            "text": i.text,
            "tags": i.tags or [],
            "id_prefix": str(i.id)[:8],
        }
        for i in result.scalars().all()
    ]

    # Unread reading items
    result = await db.execute(
        select(ReadingItem)
        .where(ReadingItem.is_read == False)
        .order_by(desc(ReadingItem.created_at))
        .limit(MAX_READING)
    )
    context["reading"] = [
        {
            "title": r.title,
            "url": r.url,
            "id_prefix": str(r.id)[:8],
        }
        for r in result.scalars().all()
    ]

    # Habits — active ones
    result = await db.execute(select(Habit).where(Habit.is_active == True))
    context["habits"] = [
        {
            "name": h.name,
            "streak": h.current_streak,
            "best_streak": h.best_streak,
            "frequency": h.frequency.value,
        }
        for h in result.scalars().all()
    ]

    # Goals — active ones
    result = await db.execute(
        select(Goal).where(Goal.status == GoalStatus.ACTIVE)
    )
    context["goals"] = [
        {
            "title": g.title,
            "progress": f"{round(g.progress * 100)}%",
            "id_prefix": str(g.id)[:8],
        }
        for g in result.scalars().all()
    ]

    # Journal — recent entries
    result = await db.execute(
        select(JournalEntry)
        .order_by(desc(JournalEntry.created_at))
        .limit(MAX_JOURNAL)
    )
    context["journal"] = [
        {
            "content": j.content[:120],
            "mood": j.mood.value if j.mood else None,
            "date": j.created_at.strftime("%b %d"),
        }
        for j in result.scalars().all()
    ]

    # Agents — all with status info
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
