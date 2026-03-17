from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import ReadingItem

router = APIRouter()


class ReadingCreate(BaseModel):
    title: str
    url: str | None = None
    tags: list[str] = []
    source: str = "manual"


class ReadingUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    is_read: bool | None = None
    notes: str | None = None
    tags: list[str] | None = None


@router.get("")
async def list_reading(show_read: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(ReadingItem).order_by(ReadingItem.created_at.desc())
    if not show_read:
        query = query.where(ReadingItem.is_read == False)
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "url": r.url,
            "is_read": r.is_read,
            "notes": r.notes,
            "tags": r.tags or [],
            "source": r.source,
            "created_at": r.created_at.isoformat(),
        }
        for r in items
    ]


@router.post("")
async def create_reading(data: ReadingCreate, db: AsyncSession = Depends(get_db)):
    item = ReadingItem(**data.model_dump())
    db.add(item)
    await db.flush()
    return {"id": str(item.id), "title": item.title}


@router.patch("/{item_id}")
async def update_reading(item_id: UUID, data: ReadingUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(ReadingItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reading item not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    if data.is_read and not item.read_at:
        item.read_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": str(item.id), "updated": True}


@router.delete("/{item_id}")
async def delete_reading(item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(ReadingItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reading item not found")
    await db.delete(item)
    return {"deleted": True}
