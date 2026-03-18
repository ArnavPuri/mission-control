from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import MarketingContent, ContentStatus, EventLog
from app.api.ws import broadcast

router = APIRouter()


class ContentCreate(BaseModel):
    title: str
    body: str
    channel: str
    signal_id: str | None = None
    project_id: str | None = None
    tags: list[str] = []
    notes: str | None = None


class ContentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    posted_url: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    project_id: str | None = None


def _serialize(c: MarketingContent) -> dict:
    return {
        "id": str(c.id),
        "title": c.title,
        "body": c.body,
        "channel": c.channel,
        "status": c.status.value,
        "source": c.source,
        "signal_id": str(c.signal_id) if c.signal_id else None,
        "project_id": str(c.project_id) if c.project_id else None,
        "agent_id": str(c.agent_id) if c.agent_id else None,
        "posted_url": c.posted_url,
        "posted_at": c.posted_at.isoformat() if c.posted_at else None,
        "notes": c.notes,
        "tags": c.tags or [],
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("")
async def list_content(
    status: str | None = None,
    channel: str | None = None,
    project_id: str | None = None,
    signal_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(MarketingContent).order_by(MarketingContent.created_at.desc())
    if status:
        query = query.where(MarketingContent.status == ContentStatus(status))
    if channel:
        query = query.where(MarketingContent.channel == channel)
    if project_id:
        query = query.where(MarketingContent.project_id == UUID(project_id))
    if signal_id:
        query = query.where(MarketingContent.signal_id == UUID(signal_id))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return [_serialize(c) for c in result.scalars().all()]


@router.get("/{content_id}")
async def get_content(content_id: UUID, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return _serialize(content)


@router.post("")
async def create_content(data: ContentCreate, db: AsyncSession = Depends(get_db)):
    content = MarketingContent(
        title=data.title,
        body=data.body,
        channel=data.channel,
        signal_id=UUID(data.signal_id) if data.signal_id else None,
        project_id=UUID(data.project_id) if data.project_id else None,
        tags=data.tags,
        notes=data.notes,
    )
    db.add(content)
    await db.flush()
    event = EventLog(
        event_type="content.created", entity_type="content",
        entity_id=content.id, source=content.source,
        data={"title": content.title, "channel": content.channel},
    )
    db.add(event)
    await broadcast("content.created", {"id": str(content.id), "title": content.title})

    # Evaluate conditional triggers
    try:
        from app.api.triggers import evaluate_triggers
        await evaluate_triggers("content", "created", {
            "title": content.title, "channel": content.channel, "tags": content.tags or [],
        }, db)
    except Exception:
        pass  # triggers are best-effort

    return _serialize(content)


@router.patch("/{content_id}")
async def update_content(content_id: UUID, data: ContentUpdate, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        new_status = ContentStatus(updates["status"])
        updates["status"] = new_status
        if new_status == ContentStatus.POSTED and not content.posted_at:
            updates["posted_at"] = datetime.now(timezone.utc)
    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None
    for key, val in updates.items():
        setattr(content, key, val)
    await db.flush()
    return _serialize(content)


@router.delete("/{content_id}")
async def delete_content(content_id: UUID, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(content)
    return {"deleted": True}
