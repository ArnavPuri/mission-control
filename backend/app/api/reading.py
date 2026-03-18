import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import ReadingItem

logger = logging.getLogger(__name__)

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
        # Auto-summarize in background if URL is present and no notes yet
        if item.url and not item.notes:
            asyncio.create_task(_auto_summarize(str(item.id), item.url, item.title))
    await db.flush()
    return {"id": str(item.id), "updated": True}


@router.post("/{item_id}/summarize")
async def summarize_reading(item_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger summarization for a reading item."""
    item = await db.get(ReadingItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reading item not found")
    if not item.url:
        raise HTTPException(status_code=400, detail="No URL to summarize")

    summary = await _generate_summary(item.url, item.title)
    if summary:
        item.notes = summary
        await db.flush()
        return {"id": str(item.id), "summary": summary}
    raise HTTPException(status_code=502, detail="Failed to generate summary")


@router.delete("/{item_id}")
async def delete_reading(item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(ReadingItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reading item not found")
    await db.delete(item)
    return {"deleted": True}


async def _generate_summary(url: str, title: str) -> str | None:
    """Generate a summary of an article using LLM."""
    from app.config import settings
    import httpx

    if not settings.anthropic_api_key and not settings.claude_code_oauth_token:
        return None

    headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
    if settings.anthropic_api_key:
        headers["x-api-key"] = settings.anthropic_api_key
    elif settings.claude_code_oauth_token:
        headers["Authorization"] = f"Bearer {settings.claude_code_oauth_token}"

    prompt = (
        f"Summarize this article in 2-3 sentences. Be concise and capture the key points.\n\n"
        f"Title: {title}\nURL: {url}\n\n"
        f"If you cannot access the URL, provide a brief summary based on the title alone."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": settings.default_model,
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

        if resp.status_code != 200:
            return None

        data = resp.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.warning(f"Auto-summarize failed for {url}: {e}")
        return None


async def _auto_summarize(item_id: str, url: str, title: str):
    """Background task: summarize and save to DB."""
    from app.db.session import async_session

    summary = await _generate_summary(url, title)
    if not summary:
        return

    try:
        async with async_session() as db:
            item = await db.get(ReadingItem, UUID(item_id))
            if item and not item.notes:
                item.notes = f"[Auto-summary] {summary}"
                await db.commit()
                logger.info(f"Auto-summarized reading item: {title[:50]}")
    except Exception as e:
        logger.warning(f"Failed to save auto-summary: {e}")
