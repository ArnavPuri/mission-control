from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models import MarketingSignal, SignalStatus, EventLog
from app.api.ws import broadcast

router = APIRouter()


class SignalCreate(BaseModel):
    title: str
    body: str = ""
    source_type: str
    signal_type: str
    source_url: str | None = None
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    channel_metadata: dict = {}
    project_id: str | None = None
    tags: list[str] = []


class SignalUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    project_id: str | None = None


def _serialize(s: MarketingSignal) -> dict:
    return {
        "id": str(s.id),
        "title": s.title,
        "body": s.body,
        "source": s.source,
        "source_type": s.source_type,
        "source_url": s.source_url,
        "relevance_score": s.relevance_score,
        "signal_type": s.signal_type,
        "status": s.status.value,
        "channel_metadata": s.channel_metadata or {},
        "project_id": str(s.project_id) if s.project_id else None,
        "agent_id": str(s.agent_id) if s.agent_id else None,
        "tags": s.tags or [],
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("")
async def list_signals(
    status: str | None = None,
    source_type: str | None = None,
    signal_type: str | None = None,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(MarketingSignal).order_by(MarketingSignal.created_at.desc())
    if status:
        query = query.where(MarketingSignal.status == SignalStatus(status))
    if source_type:
        query = query.where(MarketingSignal.source_type == source_type)
    if signal_type:
        query = query.where(MarketingSignal.signal_type == signal_type)
    if project_id:
        query = query.where(MarketingSignal.project_id == UUID(project_id))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return [_serialize(s) for s in result.scalars().all()]


@router.get("/{signal_id}")
async def get_signal(signal_id: UUID, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _serialize(signal)


@router.post("")
async def create_signal(data: SignalCreate, db: AsyncSession = Depends(get_db)):
    signal = MarketingSignal(
        title=data.title,
        body=data.body,
        source_type=data.source_type,
        signal_type=data.signal_type,
        source_url=data.source_url,
        relevance_score=data.relevance_score,
        channel_metadata=data.channel_metadata,
        project_id=UUID(data.project_id) if data.project_id else None,
        tags=data.tags,
    )
    db.add(signal)
    await db.flush()
    event = EventLog(
        event_type="signal.created", entity_type="signal",
        entity_id=signal.id, source=signal.source,
        data={"title": signal.title, "signal_type": signal.signal_type},
    )
    db.add(event)
    await broadcast("signal.created", {"id": str(signal.id), "title": signal.title})
    return _serialize(signal)


@router.patch("/{signal_id}")
async def update_signal(signal_id: UUID, data: SignalUpdate, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        updates["status"] = SignalStatus(updates["status"])
    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None
    for key, val in updates.items():
        setattr(signal, key, val)
    await db.flush()
    return _serialize(signal)


@router.delete("/{signal_id}")
async def delete_signal(signal_id: UUID, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    await db.delete(signal)
    return {"deleted": True}
