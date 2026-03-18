from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Note

router = APIRouter()


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []
    is_pinned: bool = False
    project_id: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    is_pinned: bool | None = None
    project_id: str | None = None


@router.get("")
async def list_notes(
    tag: str | None = None,
    pinned_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(Note).order_by(Note.is_pinned.desc(), Note.updated_at.desc())
    if tag:
        query = query.where(Note.tags.any(tag))
    if pinned_only:
        query = query.where(Note.is_pinned == True)
    result = await db.execute(query)
    notes = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "content": n.content,
            "tags": n.tags or [],
            "is_pinned": n.is_pinned,
            "project_id": str(n.project_id) if n.project_id else None,
            "source": n.source,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat() if n.updated_at else n.created_at.isoformat(),
        }
        for n in notes
    ]


@router.get("/{note_id}")
async def get_note(note_id: UUID, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {
        "id": str(note.id),
        "title": note.title,
        "content": note.content,
        "tags": note.tags or [],
        "is_pinned": note.is_pinned,
        "project_id": str(note.project_id) if note.project_id else None,
        "source": note.source,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat() if note.updated_at else note.created_at.isoformat(),
    }


@router.post("")
async def create_note(data: NoteCreate, db: AsyncSession = Depends(get_db)):
    note = Note(**data.model_dump())
    db.add(note)
    await db.flush()
    return {"id": str(note.id), "title": note.title}


@router.patch("/{note_id}")
async def update_note(note_id: UUID, data: NoteUpdate, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(note, key, val)
    await db.flush()
    return {"id": str(note.id), "updated": True}


@router.delete("/{note_id}")
async def delete_note(note_id: UUID, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    return {"deleted": True}
