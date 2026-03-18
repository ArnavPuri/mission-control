"""Deduplication API — detect near-duplicate tasks and ideas."""

from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Task, Idea, TaskStatus

router = APIRouter()


def _similarity(a: str, b: str) -> float:
    """Compute text similarity between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class DuplicateGroup(BaseModel):
    items: list[dict]
    similarity: float


class CheckDuplicateRequest(BaseModel):
    text: str
    entity_type: str = "task"  # task or idea


@router.get("/tasks")
async def find_duplicate_tasks(
    threshold: float = Query(0.7, ge=0.5, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Find groups of near-duplicate tasks."""
    result = await db.execute(
        select(Task).where(Task.status != TaskStatus.DONE).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()

    seen: set[str] = set()
    groups: list[dict] = []

    for i, t1 in enumerate(tasks):
        if str(t1.id) in seen:
            continue
        group = [{
            "id": str(t1.id),
            "text": t1.text,
            "status": t1.status.value,
            "created_at": t1.created_at.isoformat(),
        }]
        best_sim = 0.0
        for t2 in tasks[i + 1:]:
            if str(t2.id) in seen:
                continue
            sim = _similarity(t1.text, t2.text)
            if sim >= threshold:
                group.append({
                    "id": str(t2.id),
                    "text": t2.text,
                    "status": t2.status.value,
                    "created_at": t2.created_at.isoformat(),
                })
                seen.add(str(t2.id))
                best_sim = max(best_sim, sim)
        if len(group) > 1:
            seen.add(str(t1.id))
            groups.append({"items": group, "similarity": round(best_sim, 3)})

    return {"entity_type": "task", "threshold": threshold, "groups": groups}


@router.get("/ideas")
async def find_duplicate_ideas(
    threshold: float = Query(0.7, ge=0.5, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Find groups of near-duplicate ideas."""
    result = await db.execute(select(Idea).order_by(Idea.created_at.desc()))
    ideas = result.scalars().all()

    seen: set[str] = set()
    groups: list[dict] = []

    for i, i1 in enumerate(ideas):
        if str(i1.id) in seen:
            continue
        group = [{
            "id": str(i1.id),
            "text": i1.text,
            "score": i1.score,
            "created_at": i1.created_at.isoformat(),
        }]
        best_sim = 0.0
        for i2 in ideas[i + 1:]:
            if str(i2.id) in seen:
                continue
            sim = _similarity(i1.text, i2.text)
            if sim >= threshold:
                group.append({
                    "id": str(i2.id),
                    "text": i2.text,
                    "score": i2.score,
                    "created_at": i2.created_at.isoformat(),
                })
                seen.add(str(i2.id))
                best_sim = max(best_sim, sim)
        if len(group) > 1:
            seen.add(str(i1.id))
            groups.append({"items": group, "similarity": round(best_sim, 3)})

    return {"entity_type": "idea", "threshold": threshold, "groups": groups}


@router.post("/check")
async def check_duplicate(data: CheckDuplicateRequest, db: AsyncSession = Depends(get_db)):
    """Check if a new text would be a duplicate before creating it."""
    threshold = 0.7
    matches: list[dict] = []

    if data.entity_type == "task":
        result = await db.execute(
            select(Task).where(Task.status != TaskStatus.DONE).order_by(Task.created_at.desc())
        )
        for t in result.scalars().all():
            sim = _similarity(data.text, t.text)
            if sim >= threshold:
                matches.append({
                    "id": str(t.id),
                    "text": t.text,
                    "similarity": round(sim, 3),
                    "entity_type": "task",
                })
    else:
        result = await db.execute(select(Idea).order_by(Idea.created_at.desc()))
        for idea in result.scalars().all():
            sim = _similarity(data.text, idea.text)
            if sim >= threshold:
                matches.append({
                    "id": str(idea.id),
                    "text": idea.text,
                    "similarity": round(sim, 3),
                    "entity_type": "idea",
                })

    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "text": data.text,
        "is_duplicate": len(matches) > 0,
        "matches": matches[:5],
    }
