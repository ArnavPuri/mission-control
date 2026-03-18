"""Routines API — morning/evening routines as checklists."""

from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Routine, RoutineItem, RoutineCompletion, RoutineType

router = APIRouter()


class RoutineItemCreate(BaseModel):
    text: str
    sort_order: int = 0
    duration_minutes: int | None = None


class RoutineCreate(BaseModel):
    name: str
    description: str = ""
    routine_type: RoutineType = RoutineType.CUSTOM
    days: list[str] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    items: list[RoutineItemCreate] = []


class RoutineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    routine_type: RoutineType | None = None
    is_active: bool | None = None
    days: list[str] | None = None


class RoutineItemUpdate(BaseModel):
    text: str | None = None
    sort_order: int | None = None
    duration_minutes: int | None = None


class RoutineCompleteRequest(BaseModel):
    completed_items: list[str] = []  # item IDs that were completed


def _serialize_routine(r: Routine) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "description": r.description,
        "routine_type": r.routine_type.value,
        "is_active": r.is_active,
        "days": r.days or [],
        "items": [
            {
                "id": str(item.id),
                "text": item.text,
                "sort_order": item.sort_order,
                "duration_minutes": item.duration_minutes,
            }
            for item in (r.items or [])
        ],
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("")
async def list_routines(
    active_only: bool = True,
    routine_type: RoutineType | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Routine).order_by(Routine.routine_type, Routine.name)
    if active_only:
        query = query.where(Routine.is_active == True)
    if routine_type:
        query = query.where(Routine.routine_type == routine_type)
    result = await db.execute(query)
    routines = result.scalars().all()
    return [_serialize_routine(r) for r in routines]


@router.post("")
async def create_routine(data: RoutineCreate, db: AsyncSession = Depends(get_db)):
    routine = Routine(
        name=data.name,
        description=data.description,
        routine_type=data.routine_type,
        days=data.days,
    )
    db.add(routine)
    await db.flush()

    for i, item_data in enumerate(data.items):
        item = RoutineItem(
            routine_id=routine.id,
            text=item_data.text,
            sort_order=item_data.sort_order or i,
            duration_minutes=item_data.duration_minutes,
        )
        db.add(item)
    await db.flush()

    # Reload to get items
    await db.refresh(routine)
    return _serialize_routine(routine)


@router.get("/{routine_id}")
async def get_routine(routine_id: UUID, db: AsyncSession = Depends(get_db)):
    routine = await db.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _serialize_routine(routine)


@router.patch("/{routine_id}")
async def update_routine(routine_id: UUID, data: RoutineUpdate, db: AsyncSession = Depends(get_db)):
    routine = await db.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(routine, key, val)
    await db.flush()
    return {"id": str(routine.id), "updated": True}


@router.delete("/{routine_id}")
async def delete_routine(routine_id: UUID, db: AsyncSession = Depends(get_db)):
    routine = await db.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    await db.delete(routine)
    return {"deleted": True}


# --- Items ---

@router.post("/{routine_id}/items")
async def add_item(routine_id: UUID, data: RoutineItemCreate, db: AsyncSession = Depends(get_db)):
    routine = await db.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    item = RoutineItem(
        routine_id=routine_id,
        text=data.text,
        sort_order=data.sort_order,
        duration_minutes=data.duration_minutes,
    )
    db.add(item)
    await db.flush()
    return {"id": str(item.id), "text": item.text}


@router.patch("/{routine_id}/items/{item_id}")
async def update_item(routine_id: UUID, item_id: UUID, data: RoutineItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(RoutineItem, item_id)
    if not item or item.routine_id != routine_id:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    await db.flush()
    return {"id": str(item.id), "updated": True}


@router.delete("/{routine_id}/items/{item_id}")
async def delete_item(routine_id: UUID, item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(RoutineItem, item_id)
    if not item or item.routine_id != routine_id:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    return {"deleted": True}


# --- Completions ---

@router.post("/{routine_id}/complete")
async def complete_routine(routine_id: UUID, data: RoutineCompleteRequest, db: AsyncSession = Depends(get_db)):
    routine = await db.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    total = len(routine.items) if routine.items else 0
    completion = RoutineCompletion(
        routine_id=routine_id,
        completed_items=data.completed_items,
        total_items=total,
    )
    db.add(completion)
    await db.flush()
    return {
        "id": str(completion.id),
        "completed": len(data.completed_items),
        "total": total,
    }


@router.get("/{routine_id}/completions")
async def list_completions(routine_id: UUID, limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RoutineCompletion)
        .where(RoutineCompletion.routine_id == routine_id)
        .order_by(RoutineCompletion.completed_at.desc())
        .limit(limit)
    )
    completions = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "completed_items": c.completed_items or [],
            "total_items": c.total_items,
            "completed_at": c.completed_at.isoformat(),
        }
        for c in completions
    ]
