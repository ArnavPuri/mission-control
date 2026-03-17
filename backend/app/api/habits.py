from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Habit, HabitCompletion, HabitFrequency

router = APIRouter()


class HabitCreate(BaseModel):
    name: str
    description: str = ""
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_days: list[str] = []
    color: str = "#00ffc8"
    project_id: UUID | None = None


class HabitUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    frequency: HabitFrequency | None = None
    target_days: list[str] | None = None
    color: str | None = None
    is_active: bool | None = None


def _serialize_habit(h: Habit) -> dict:
    today = datetime.now(timezone.utc).date()
    completed_today = any(
        c.completed_at.date() == today for c in (h.completions or [])
    )
    return {
        "id": str(h.id),
        "name": h.name,
        "description": h.description,
        "frequency": h.frequency.value,
        "target_days": h.target_days or [],
        "current_streak": h.current_streak,
        "best_streak": h.best_streak,
        "total_completions": h.total_completions,
        "is_active": h.is_active,
        "color": h.color,
        "completed_today": completed_today,
        "project_id": str(h.project_id) if h.project_id else None,
        "created_at": h.created_at.isoformat(),
    }


@router.get("")
async def list_habits(active_only: bool = True, db: AsyncSession = Depends(get_db)):
    query = select(Habit).order_by(Habit.created_at)
    if active_only:
        query = query.where(Habit.is_active == True)
    result = await db.execute(query)
    return [_serialize_habit(h) for h in result.scalars().all()]


@router.post("")
async def create_habit(data: HabitCreate, db: AsyncSession = Depends(get_db)):
    habit = Habit(**data.model_dump())
    db.add(habit)
    await db.flush()
    return {"id": str(habit.id), "name": habit.name}


@router.patch("/{habit_id}")
async def update_habit(habit_id: UUID, data: HabitUpdate, db: AsyncSession = Depends(get_db)):
    habit = await db.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(habit, key, val)
    await db.flush()
    return {"id": str(habit.id), "updated": True}


@router.post("/{habit_id}/complete")
async def complete_habit(habit_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark a habit as completed for today."""
    habit = await db.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    today = datetime.now(timezone.utc).date()
    already = any(c.completed_at.date() == today for c in (habit.completions or []))
    if already:
        raise HTTPException(status_code=409, detail="Already completed today")

    completion = HabitCompletion(habit_id=habit_id)
    db.add(completion)

    # Update streak
    yesterday = today - timedelta(days=1)
    had_yesterday = any(c.completed_at.date() == yesterday for c in (habit.completions or []))
    if had_yesterday or habit.current_streak == 0:
        habit.current_streak += 1
    else:
        habit.current_streak = 1

    habit.best_streak = max(habit.best_streak, habit.current_streak)
    habit.total_completions += 1
    await db.flush()

    return {
        "id": str(habit.id),
        "current_streak": habit.current_streak,
        "best_streak": habit.best_streak,
        "completed": True,
    }


@router.post("/{habit_id}/uncomplete")
async def uncomplete_habit(habit_id: UUID, db: AsyncSession = Depends(get_db)):
    """Remove today's completion for a habit."""
    habit = await db.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    today = datetime.now(timezone.utc).date()
    for c in (habit.completions or []):
        if c.completed_at.date() == today:
            await db.delete(c)
            habit.current_streak = max(0, habit.current_streak - 1)
            habit.total_completions = max(0, habit.total_completions - 1)
            await db.flush()
            return {"id": str(habit.id), "uncompleted": True}

    raise HTTPException(status_code=404, detail="No completion found for today")


@router.delete("/{habit_id}")
async def delete_habit(habit_id: UUID, db: AsyncSession = Depends(get_db)):
    habit = await db.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    await db.delete(habit)
    return {"deleted": True}
