from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import JournalEntry, MoodLevel

router = APIRouter()


class JournalCreate(BaseModel):
    content: str
    mood: MoodLevel | None = None
    energy: int | None = None  # 1-5
    tags: list[str] = []
    wins: list[str] = []
    challenges: list[str] = []
    gratitude: list[str] = []
    source: str = "manual"


class JournalUpdate(BaseModel):
    content: str | None = None
    mood: MoodLevel | None = None
    energy: int | None = None
    tags: list[str] | None = None
    wins: list[str] | None = None
    challenges: list[str] | None = None
    gratitude: list[str] | None = None


def _serialize_entry(e: JournalEntry) -> dict:
    return {
        "id": str(e.id),
        "content": e.content,
        "mood": e.mood.value if e.mood else None,
        "energy": e.energy,
        "tags": e.tags or [],
        "wins": e.wins or [],
        "challenges": e.challenges or [],
        "gratitude": e.gratitude or [],
        "source": e.source,
        "created_at": e.created_at.isoformat(),
    }


@router.get("")
async def list_entries(limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JournalEntry).order_by(desc(JournalEntry.created_at)).limit(limit)
    )
    return [_serialize_entry(e) for e in result.scalars().all()]


@router.post("")
async def create_entry(data: JournalCreate, db: AsyncSession = Depends(get_db)):
    entry = JournalEntry(**data.model_dump())
    db.add(entry)
    await db.flush()
    return {"id": str(entry.id), "created": True}


@router.get("/{entry_id}")
async def get_entry(entry_id: UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return _serialize_entry(entry)


@router.patch("/{entry_id}")
async def update_entry(entry_id: UUID, data: JournalUpdate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, val)
    await db.flush()
    return {"id": str(entry.id), "updated": True}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    await db.delete(entry)
    return {"deleted": True}
