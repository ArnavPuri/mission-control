"""
In-app notification center.

Stores notifications for dashboard display. Notifications are generated
from agent completions, approval requests, system events, etc.
"""

from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Base, Column, String, Text, Boolean, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid as _uuid

router = APIRouter()


class Notification(Base):
    """In-app notification for the dashboard."""
    __tablename__ = "notifications"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    category = Column(String(50), default="info")  # info, success, warning, error, approval
    source = Column(String(100), default="system")  # agent:<name>, system, webhook:<name>
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)  # optional deep link
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_notifications_read", "is_read"),
        Index("idx_notifications_created", "created_at"),
    )


@router.get("")
async def list_notifications(unread_only: bool = False, limit: int = 50, db: AsyncSession = Depends(get_db)):
    query = select(Notification).order_by(desc(Notification.created_at)).limit(limit)
    if unread_only:
        query = query.where(Notification.is_read == False)
    result = await db.execute(query)
    notifs = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "category": n.category,
            "source": n.source,
            "is_read": n.is_read,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifs
    ]


@router.get("/count")
async def unread_count(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count(Notification.id)).where(Notification.is_read == False)
    )
    return {"unread": count}


@router.post("/{notif_id}/read")
async def mark_read(notif_id: UUID, db: AsyncSession = Depends(get_db)):
    notif = await db.get(Notification, notif_id)
    if notif:
        notif.is_read = True
        await db.flush()
    return {"read": True}


@router.post("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Notification).where(Notification.is_read == False).values(is_read=True)
    )
    await db.flush()
    return {"read_all": True}


# ─── Helper to create notifications from anywhere ───

async def create_notification(
    db: AsyncSession,
    title: str,
    body: str = "",
    category: str = "info",
    source: str = "system",
    action_url: str | None = None,
    data: dict | None = None,
):
    """Create a notification and broadcast via WebSocket."""
    from app.api.ws import broadcast

    notif = Notification(
        title=title, body=body, category=category,
        source=source, action_url=action_url, data=data or {},
    )
    db.add(notif)
    await db.flush()
    await broadcast("notification.new", {
        "id": str(notif.id),
        "title": title,
        "category": category,
        "source": source,
    })
    return notif
