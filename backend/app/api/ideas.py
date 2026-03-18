from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Idea

router = APIRouter()


class IdeaCreate(BaseModel):
    text: str
    tags: list[str] = []
    source: str = "manual"
    project_id: UUID | None = None


@router.get("")
async def list_ideas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Idea).order_by(Idea.created_at.desc()))
    ideas = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "text": i.text,
            "tags": i.tags or [],
            "source": i.source,
            "score": i.score,
            "validation_notes": i.validation_notes,
            "project_id": str(i.project_id) if i.project_id else None,
            "created_at": i.created_at.isoformat(),
        }
        for i in ideas
    ]


@router.post("")
async def create_idea(data: IdeaCreate, db: AsyncSession = Depends(get_db)):
    idea = Idea(**data.model_dump())
    db.add(idea)
    await db.flush()

    # Evaluate conditional triggers
    try:
        from app.api.triggers import evaluate_triggers
        await evaluate_triggers("idea", "created", {
            "text": idea.text, "tags": idea.tags or [], "source": idea.source,
        }, db)
    except Exception:
        pass  # triggers are best-effort

    return {"id": str(idea.id), "text": idea.text}


@router.delete("/{idea_id}")
async def delete_idea(idea_id: UUID, db: AsyncSession = Depends(get_db)):
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    await db.delete(idea)
    return {"deleted": True}
