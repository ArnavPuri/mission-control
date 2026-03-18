"""Auto-tagging — LLM-based classification of tasks and ideas."""

import json
import logging
import httpx
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Task, Idea
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

AUTOTAG_PROMPT = """Classify this text and return JSON with suggested tags. Return ONLY valid JSON.

Text: "{text}"

Return format: {{"tags": ["tag1", "tag2"], "category": "one-word-category"}}

Rules:
- Return 1-4 lowercase tags that describe the topic/domain
- Category should be one of: work, personal, learning, health, finance, creative, social, admin
- Tags should be specific and useful for filtering
"""


async def _classify_text(text: str) -> dict:
    """Call LLM to classify text and return tags."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="API key not configured for auto-tagging")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": settings.anthropic_api_key,
            },
            json={
                "model": settings.default_model,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": AUTOTAG_PROMPT.format(text=text[:500])}],
            },
        )
        data = resp.json()

    response_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            response_text += block["text"]

    try:
        cleaned = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"tags": [], "category": "general"}


@router.post("/task/{task_id}")
async def autotag_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """Auto-tag a task using LLM classification."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await _classify_text(task.text)
    new_tags = list(set((task.tags or []) + result.get("tags", [])))
    task.tags = new_tags
    await db.flush()

    return {"id": str(task.id), "tags": new_tags, "category": result.get("category")}


@router.post("/idea/{idea_id}")
async def autotag_idea(idea_id: UUID, db: AsyncSession = Depends(get_db)):
    """Auto-tag an idea using LLM classification."""
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    result = await _classify_text(idea.text)
    new_tags = list(set((idea.tags or []) + result.get("tags", [])))
    idea.tags = new_tags
    await db.flush()

    return {"id": str(idea.id), "tags": new_tags, "category": result.get("category")}


@router.post("/batch")
async def autotag_batch(
    entity_type: str = "tasks",
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Auto-tag multiple untagged items."""
    if entity_type == "tasks":
        result = await db.execute(
            select(Task).where(Task.tags == None).limit(limit)  # noqa: E711
        )
        items = result.scalars().all()
        tagged = []
        for item in items:
            try:
                classification = await _classify_text(item.text)
                item.tags = classification.get("tags", [])
                tagged.append({"id": str(item.id), "tags": item.tags})
            except Exception as e:
                logger.warning(f"Auto-tag failed for task {item.id}: {e}")
        await db.flush()
        return {"tagged": len(tagged), "items": tagged}

    elif entity_type == "ideas":
        result = await db.execute(
            select(Idea).where(Idea.tags == None).limit(limit)  # noqa: E711
        )
        items = result.scalars().all()
        tagged = []
        for item in items:
            try:
                classification = await _classify_text(item.text)
                item.tags = classification.get("tags", [])
                tagged.append({"id": str(item.id), "tags": item.tags})
            except Exception as e:
                logger.warning(f"Auto-tag failed for idea {item.id}: {e}")
        await db.flush()
        return {"tagged": len(tagged), "items": tagged}

    raise HTTPException(status_code=400, detail="entity_type must be 'tasks' or 'ideas'")
