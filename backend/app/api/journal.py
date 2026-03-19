from difflib import SequenceMatcher
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
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

    # Evaluate conditional triggers
    try:
        from app.api.triggers import evaluate_triggers
        await evaluate_triggers("journal", "created", {
            "content": entry.content[:200], "mood": entry.mood.value if entry.mood else None,
            "energy": entry.energy, "tags": entry.tags or [], "source": entry.source,
        }, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Trigger evaluation failed: {e}")

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


@router.get("/search")
async def search_journal(
    q: str = Query(..., min_length=1),
    mode: str = Query("semantic", description="Search mode: 'text' or 'semantic'"),
    limit: int = Query(20, ge=1, le=100),
    mood: MoodLevel | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search journal entries by text or semantic similarity.

    - text mode: simple case-insensitive substring matching
    - semantic mode: ranks results by text similarity (SequenceMatcher)
    """
    query = select(JournalEntry).order_by(desc(JournalEntry.created_at))
    if mood:
        query = query.where(JournalEntry.mood == mood)

    result = await db.execute(query)
    all_entries = result.scalars().all()

    if mode == "text":
        q_lower = q.lower()
        matched = [
            e for e in all_entries
            if q_lower in e.content.lower()
            or any(q_lower in w.lower() for w in (e.wins or []))
            or any(q_lower in c.lower() for c in (e.challenges or []))
            or any(q_lower in g.lower() for g in (e.gratitude or []))
        ]
        return {
            "query": q,
            "mode": "text",
            "total": len(matched),
            "results": [
                {**_serialize_entry(e), "relevance": 1.0}
                for e in matched[:limit]
            ],
        }

    # Semantic mode: score all entries by similarity to query
    scored = []
    q_lower = q.lower()
    for entry in all_entries:
        # Score based on content similarity
        content_sim = SequenceMatcher(None, q_lower, entry.content.lower()[:500]).ratio()

        # Boost for keyword presence in structured fields
        boost = 0.0
        full_text = entry.content.lower()
        for word in q_lower.split():
            if word in full_text:
                boost += 0.1
        for w in (entry.wins or []):
            if any(word in w.lower() for word in q_lower.split()):
                boost += 0.05
        for c in (entry.challenges or []):
            if any(word in c.lower() for word in q_lower.split()):
                boost += 0.05
        for tag in (entry.tags or []):
            if any(word in tag.lower() for word in q_lower.split()):
                boost += 0.1

        score = min(content_sim + boost, 1.0)
        if score > 0.05:  # minimum threshold
            scored.append((entry, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    return {
        "query": q,
        "mode": "semantic",
        "total": len(scored),
        "results": [
            {**_serialize_entry(e), "relevance": round(score, 3)}
            for e, score in scored[:limit]
        ],
    }
