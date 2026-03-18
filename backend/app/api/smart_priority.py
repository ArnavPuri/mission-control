"""Smart Prioritization API — suggest priority for tasks based on patterns."""

import re
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Task, TaskStatus, TaskPriority

router = APIRouter()

# Keyword signals for priority detection
CRITICAL_KEYWORDS = {"urgent", "asap", "emergency", "critical", "blocker", "p0", "immediately", "broken", "outage", "down"}
HIGH_KEYWORDS = {"important", "deadline", "overdue", "bug", "fix", "security", "deploy", "release", "p1", "launch"}
LOW_KEYWORDS = {"nice to have", "someday", "maybe", "minor", "cleanup", "refactor", "cosmetic", "p3", "low priority"}


def _suggest_priority(text: str, existing_tasks: list[dict]) -> dict:
    """Suggest a priority based on keyword analysis and historical patterns."""
    text_lower = text.lower()
    scores = {"critical": 0.0, "high": 0.0, "medium": 0.0, "low": 0.0}

    # 1. Keyword matching
    for kw in CRITICAL_KEYWORDS:
        if kw in text_lower:
            scores["critical"] += 3.0
    for kw in HIGH_KEYWORDS:
        if kw in text_lower:
            scores["high"] += 2.0
    for kw in LOW_KEYWORDS:
        if kw in text_lower:
            scores["low"] += 2.0

    # 2. Historical pattern matching — find similar past tasks by word overlap
    text_words = set(re.findall(r'\w+', text_lower))
    if text_words and existing_tasks:
        weighted_counts: Counter = Counter()
        total_similarity = 0.0
        for t in existing_tasks:
            task_words = set(re.findall(r'\w+', t["text"].lower()))
            overlap = len(text_words & task_words)
            if overlap >= 2:  # at least 2 shared words
                similarity = overlap / max(len(text_words | task_words), 1)
                weighted_counts[t["priority"]] += similarity
                total_similarity += similarity

        if total_similarity > 0:
            for pri, weight in weighted_counts.items():
                normalized = weight / total_similarity
                scores[pri] += normalized * 2.0  # scale the pattern signal

    # 3. Default bias toward medium
    scores["medium"] += 0.5

    # Pick the winner
    suggested = max(scores, key=lambda k: scores[k])
    confidence = scores[suggested] / (sum(scores.values()) or 1)

    reasons = []
    if any(kw in text_lower for kw in CRITICAL_KEYWORDS):
        reasons.append("Contains urgent keywords")
    if any(kw in text_lower for kw in HIGH_KEYWORDS):
        reasons.append("Contains high-priority keywords")
    if any(kw in text_lower for kw in LOW_KEYWORDS):
        reasons.append("Contains low-priority keywords")
    if existing_tasks:
        reasons.append(f"Analyzed {len(existing_tasks)} similar past tasks")

    return {
        "suggested_priority": suggested,
        "confidence": round(confidence, 2),
        "scores": {k: round(v, 2) for k, v in scores.items()},
        "reasons": reasons,
    }


class PrioritySuggestRequest(BaseModel):
    text: str


@router.post("/suggest")
async def suggest_priority(data: PrioritySuggestRequest, db: AsyncSession = Depends(get_db)):
    """Suggest a priority for new task text based on keywords and historical patterns."""
    # Load recent completed and active tasks for pattern matching
    result = await db.execute(
        select(Task).order_by(Task.created_at.desc()).limit(200)
    )
    existing = [
        {"text": t.text, "priority": t.priority.value, "status": t.status.value}
        for t in result.scalars().all()
    ]
    return _suggest_priority(data.text, existing)


@router.post("/bulk-suggest")
async def bulk_suggest(db: AsyncSession = Depends(get_db)):
    """Re-evaluate priorities for all open tasks and return suggestions."""
    result = await db.execute(
        select(Task).where(Task.status != TaskStatus.DONE).order_by(Task.created_at.desc())
    )
    open_tasks = result.scalars().all()

    # Load all tasks for pattern matching
    all_result = await db.execute(
        select(Task).where(Task.status == TaskStatus.DONE).order_by(Task.created_at.desc()).limit(200)
    )
    completed_tasks = [
        {"text": t.text, "priority": t.priority.value, "status": t.status.value}
        for t in all_result.scalars().all()
    ]

    suggestions = []
    for task in open_tasks:
        suggestion = _suggest_priority(task.text, completed_tasks)
        if suggestion["suggested_priority"] != task.priority.value:
            suggestions.append({
                "task_id": str(task.id),
                "text": task.text,
                "current_priority": task.priority.value,
                **suggestion,
            })

    return {"suggestions": suggestions, "total_evaluated": len(open_tasks)}
