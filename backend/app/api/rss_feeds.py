import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import RSSFeed, Note, EventLog

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedCreate(BaseModel):
    title: str
    url: str
    tags: list[str] = []
    fetch_interval_minutes: int = 60


class FeedUpdate(BaseModel):
    title: str | None = None
    is_active: bool | None = None
    tags: list[str] | None = None
    fetch_interval_minutes: int | None = None


@router.get("")
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RSSFeed).order_by(RSSFeed.created_at.desc()))
    feeds = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "title": f.title,
            "url": f.url,
            "is_active": f.is_active,
            "tags": f.tags or [],
            "fetch_interval_minutes": f.fetch_interval_minutes,
            "last_fetched_at": f.last_fetched_at.isoformat() if f.last_fetched_at else None,
            "error_count": f.error_count,
            "last_error": f.last_error,
            "created_at": f.created_at.isoformat(),
        }
        for f in feeds
    ]


@router.post("")
async def create_feed(data: FeedCreate, db: AsyncSession = Depends(get_db)):
    # Check for duplicate URL
    existing = await db.execute(select(RSSFeed).where(RSSFeed.url == data.url))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Feed URL already exists")

    feed = RSSFeed(**data.model_dump())
    db.add(feed)
    await db.flush()
    return {"id": str(feed.id), "title": feed.title}


@router.patch("/{feed_id}")
async def update_feed(feed_id: UUID, data: FeedUpdate, db: AsyncSession = Depends(get_db)):
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(feed, key, val)
    await db.flush()
    return {"id": str(feed.id), "updated": True}


@router.delete("/{feed_id}")
async def delete_feed(feed_id: UUID, db: AsyncSession = Depends(get_db)):
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    return {"deleted": True}


@router.post("/{feed_id}/fetch")
async def fetch_feed(feed_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger a feed fetch."""
    feed = await db.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    count = await _fetch_and_import(feed, db)
    return {"id": str(feed.id), "imported": count}


async def fetch_all_due_feeds(db: AsyncSession):
    """Fetch all feeds that are due for refresh. Called by scheduler."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(RSSFeed).where(RSSFeed.is_active == True))
    feeds = result.scalars().all()

    total = 0
    for feed in feeds:
        if feed.last_fetched_at:
            from datetime import timedelta
            next_fetch = feed.last_fetched_at + timedelta(minutes=feed.fetch_interval_minutes)
            if now < next_fetch:
                continue
        count = await _fetch_and_import(feed, db)
        total += count

    return total


async def _fetch_and_import(feed: RSSFeed, db: AsyncSession) -> int:
    """Fetch an RSS feed and import new items to the reading list."""
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed — pip install feedparser")
        feed.last_error = "feedparser not installed"
        feed.error_count += 1
        await db.flush()
        return 0

    try:
        parsed = feedparser.parse(feed.url)

        if parsed.bozo and not parsed.entries:
            feed.last_error = str(parsed.bozo_exception)[:500]
            feed.error_count += 1
            await db.flush()
            return 0

        imported = 0
        for entry in parsed.entries[:20]:  # Limit to 20 per fetch
            title = entry.get("title", "Untitled")
            url = entry.get("link", "")

            if not url:
                continue

            # Check if already imported (by matching URL in content)
            existing = await db.execute(
                select(Note).where(Note.content.contains(url), Note.source == "rss")
            )
            if existing.scalar_one_or_none():
                continue

            item = Note(
                title=title,
                content=f"[{title}]({url})\n\nImported from RSS feed: {feed.title}",
                source="rss",
                tags=(feed.tags or []) + [f"feed:{feed.title}"],
            )
            db.add(item)
            imported += 1

        feed.last_fetched_at = datetime.now(timezone.utc)
        feed.error_count = 0
        feed.last_error = None
        await db.flush()

        if imported > 0:
            db.add(EventLog(
                event_type="reading.imported",
                entity_type="reading",
                source="rss",
                data={"feed": feed.title, "count": imported},
            ))
            await db.flush()

        return imported

    except Exception as e:
        logger.error(f"Error fetching feed {feed.url}: {e}")
        feed.last_error = str(e)[:500]
        feed.error_count += 1
        await db.flush()
        return 0
