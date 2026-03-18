from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Goal, KeyResult, GoalStatus

router = APIRouter()


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: datetime | None = None
    project_id: UUID | None = None
    tags: list[str] = []


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GoalStatus | None = None
    target_date: datetime | None = None
    progress: float | None = None
    tags: list[str] | None = None


class KeyResultCreate(BaseModel):
    title: str
    target_value: float
    current_value: float = 0.0
    unit: str = ""


class KeyResultUpdate(BaseModel):
    title: str | None = None
    current_value: float | None = None
    target_value: float | None = None
    unit: str | None = None


def _serialize_goal(g: Goal) -> dict:
    krs = g.key_results or []
    # Auto-calculate progress from key results if any exist
    if krs:
        progress = sum(
            min(kr.current_value / kr.target_value, 1.0) if kr.target_value > 0 else 0
            for kr in krs
        ) / len(krs)
    else:
        progress = g.progress

    return {
        "id": str(g.id),
        "title": g.title,
        "description": g.description,
        "status": g.status.value,
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "progress": round(progress, 3),
        "project_id": str(g.project_id) if g.project_id else None,
        "tags": g.tags or [],
        "key_results": [
            {
                "id": str(kr.id),
                "title": kr.title,
                "target_value": kr.target_value,
                "current_value": kr.current_value,
                "unit": kr.unit,
                "progress": round(min(kr.current_value / kr.target_value, 1.0), 3) if kr.target_value > 0 else 0,
            }
            for kr in krs
        ],
        "created_at": g.created_at.isoformat(),
    }


@router.get("")
async def list_goals(status: GoalStatus | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Goal).order_by(Goal.created_at.desc())
    if status:
        query = query.where(Goal.status == status)
    result = await db.execute(query)
    return [_serialize_goal(g) for g in result.scalars().all()]


@router.post("")
async def create_goal(data: GoalCreate, db: AsyncSession = Depends(get_db)):
    goal = Goal(**data.model_dump())
    db.add(goal)
    await db.flush()

    # Evaluate conditional triggers
    try:
        from app.api.triggers import evaluate_triggers
        await evaluate_triggers("goal", "created", {
            "title": goal.title, "description": goal.description, "tags": goal.tags or [],
        }, db)
    except Exception:
        pass  # triggers are best-effort

    return {"id": str(goal.id), "title": goal.title}


@router.patch("/{goal_id}")
async def update_goal(goal_id: UUID, data: GoalUpdate, db: AsyncSession = Depends(get_db)):
    goal = await db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(goal, key, val)
    await db.flush()
    return {"id": str(goal.id), "updated": True}


@router.delete("/{goal_id}")
async def delete_goal(goal_id: UUID, db: AsyncSession = Depends(get_db)):
    goal = await db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    return {"deleted": True}


# --- Key Results ---

@router.post("/{goal_id}/key-results")
async def create_key_result(goal_id: UUID, data: KeyResultCreate, db: AsyncSession = Depends(get_db)):
    goal = await db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    kr = KeyResult(goal_id=goal_id, **data.model_dump())
    db.add(kr)
    await db.flush()
    return {"id": str(kr.id), "title": kr.title}


@router.patch("/{goal_id}/key-results/{kr_id}")
async def update_key_result(goal_id: UUID, kr_id: UUID, data: KeyResultUpdate, db: AsyncSession = Depends(get_db)):
    kr = await db.get(KeyResult, kr_id)
    if not kr or kr.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(kr, key, val)
    await db.flush()
    return {"id": str(kr.id), "updated": True}


@router.delete("/{goal_id}/key-results/{kr_id}")
async def delete_key_result(goal_id: UUID, kr_id: UUID, db: AsyncSession = Depends(get_db)):
    kr = await db.get(KeyResult, kr_id)
    if not kr or kr.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    await db.delete(kr)
    return {"deleted": True}
