import json
import re
import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db, async_session
from app.db.models import (
    Project, ProjectStatus, Task, TaskStatus, Goal, GoalStatus,
    AgentRun, AgentRunStatus, EventLog, Idea, MarketingSignal, MarketingContent,
)
from app.api.ws import broadcast
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.PLANNING
    color: str = "#00ffc8"
    url: str | None = None
    metadata: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    color: str | None = None
    url: str | None = None
    metadata: dict | None = None


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    task_count_sq = (
        select(func.count(Task.id))
        .where(Task.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    open_task_count_sq = (
        select(func.count(Task.id))
        .where(Task.project_id == Project.id, Task.status != TaskStatus.DONE)
        .correlate(Project)
        .scalar_subquery()
    )
    idea_count_sq = (
        select(func.count(Idea.id))
        .where(Idea.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    feedback_count_sq = (
        select(func.count(MarketingSignal.id))
        .where(MarketingSignal.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    content_count_sq = (
        select(func.count(MarketingContent.id))
        .where(MarketingContent.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            Project,
            task_count_sq.label("task_count"),
            open_task_count_sq.label("open_task_count"),
            idea_count_sq.label("idea_count"),
            feedback_count_sq.label("feedback_count"),
            content_count_sq.label("content_count"),
        ).order_by(Project.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "status": p.status.value,
            "color": p.color,
            "url": p.url,
            "metadata": p.metadata_ or {},
            "task_count": task_count,
            "open_task_count": open_task_count,
            "idea_count": idea_count,
            "feedback_count": feedback_count,
            "content_count": content_count,
            "agent_count": len(p.agents) if p.agents else 0,
            "created_at": p.created_at.isoformat(),
        }
        for p, task_count, open_task_count, idea_count, feedback_count, content_count in rows
    ]


@router.post("")
async def create_project(
    data: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    fields = data.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_"] = fields.pop("metadata")
    # If URL provided, set enrichment status to pending
    if fields.get("url"):
        meta = fields.get("metadata_") or {}
        meta["enrichment_status"] = "pending"
        fields["metadata_"] = meta
    project = Project(**fields)
    db.add(project)
    await db.flush()
    project_id = project.id
    # Trigger background enrichment if URL provided
    if data.url:
        background_tasks.add_task(_enrich_project, project_id, data.url)
    return {"id": str(project_id), "name": project.name}


@router.get("/{project_id}")
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    counts = await db.execute(
        select(
            func.count(Task.id).filter(Task.project_id == project_id).label("task_count"),
            func.count(Task.id).filter(Task.project_id == project_id, Task.status != TaskStatus.DONE).label("open_task_count"),
            func.count(Idea.id).filter(Idea.project_id == project_id).label("idea_count"),
            func.count(MarketingSignal.id).filter(MarketingSignal.project_id == project_id).label("feedback_count"),
            func.count(MarketingContent.id).filter(MarketingContent.project_id == project_id).label("content_count"),
        )
    )
    c = counts.one()
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value,
        "color": project.color,
        "url": project.url,
        "metadata": project.metadata_ or {},
        "task_count": c.task_count,
        "open_task_count": c.open_task_count,
        "idea_count": c.idea_count,
        "feedback_count": c.feedback_count,
        "content_count": c.content_count,
        "agent_count": len(project.agents) if project.agents else 0,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.patch("/{project_id}")
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    fields = data.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_"] = fields.pop("metadata")
    for key, val in fields.items():
        setattr(project, key, val)
    await db.flush()
    return {"id": str(project.id), "updated": True}


@router.delete("/{project_id}")
async def delete_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    return {"deleted": True}


@router.get("/{project_id}/health")
async def project_health(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Calculate project health score and return detailed metrics."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Task metrics
    all_tasks = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = all_tasks.scalars().all()
    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    overdue_tasks = sum(
        1 for t in tasks
        if t.due_date and t.due_date < now and t.status != TaskStatus.DONE
    )
    blocked_tasks = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)

    # Completion rate
    completion_rate = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Recent velocity — tasks completed in last 7 days
    recent_completions = sum(
        1 for t in tasks
        if t.status == TaskStatus.DONE
        and t.completed_at
        and t.completed_at >= seven_days_ago
    )

    # Goal progress
    goals_result = await db.execute(
        select(Goal).where(
            Goal.project_id == project_id,
            Goal.status == GoalStatus.ACTIVE,
        )
    )
    goals = goals_result.scalars().all()
    avg_goal_progress = (
        sum(g.progress for g in goals) / len(goals)
        if goals else 0
    )

    # Recent activity — events in last 30 days
    activity_count = await db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.entity_id == project_id,
            EventLog.created_at >= thirty_days_ago,
        )
    ) or 0

    # Also count task-level activity for this project
    task_ids = [t.id for t in tasks]
    if task_ids:
        task_activity = await db.scalar(
            select(func.count(EventLog.id)).where(
                EventLog.entity_id.in_(task_ids),
                EventLog.created_at >= thirty_days_ago,
            )
        ) or 0
        activity_count += task_activity

    # Calculate health score (0-100)
    score = 100
    # Penalize for overdue tasks (-5 each, max -30)
    score -= min(overdue_tasks * 5, 30)
    # Penalize for blocked tasks (-3 each, max -15)
    score -= min(blocked_tasks * 3, 15)
    # Penalize for low completion rate
    if total_tasks > 5 and completion_rate < 20:
        score -= 20
    elif total_tasks > 5 and completion_rate < 50:
        score -= 10
    # Reward recent velocity
    if recent_completions >= 5:
        score += 5
    elif recent_completions == 0 and total_tasks > 3:
        score -= 10
    # Penalize for inactivity
    if activity_count == 0 and total_tasks > 0:
        score -= 15
    # Factor in goal progress
    if goals:
        score += int(avg_goal_progress * 10)  # up to +10

    score = max(0, min(100, score))

    # Determine status color
    if score >= 70:
        status = "healthy"
    elif score >= 40:
        status = "needs_attention"
    else:
        status = "at_risk"

    return {
        "project_id": str(project_id),
        "project_name": project.name,
        "score": score,
        "status": status,
        "metrics": {
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "completion_rate": round(completion_rate, 1),
            "weekly_velocity": recent_completions,
            "active_goals": len(goals),
            "avg_goal_progress": round(avg_goal_progress * 100, 1),
            "monthly_activity": activity_count,
        },
    }


# --- Project Enrichment ---

ENRICHMENT_PROMPT = """Analyze this website content and extract brand information. Return ONLY valid JSON with these fields:

{
  "tagline": "the site's main tagline or value proposition (one line)",
  "offering": "what the product/service does (2-3 sentences)",
  "brand_voice": "description of the writing tone and style (1-2 sentences)",
  "tone_keywords": ["3-5 adjectives describing the tone"],
  "brand_colors": ["hex color codes found on the site, primary first"]
}

If you cannot determine a field, use null. Do not include any text outside the JSON.

Website content:
"""


def _strip_html_to_text(html: str) -> str:
    """Strip HTML tags and extract readable text content."""
    # Remove script and style blocks
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Extract hex colors before stripping tags
    colors = re.findall(r"#[0-9a-fA-F]{6}", html)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Prepend found colors as context
    if colors:
        unique_colors = list(dict.fromkeys(colors))[:10]
        text = f"[CSS colors found: {', '.join(unique_colors)}]\n\n{text}"
    return text[:4000]


async def _call_haiku(prompt: str) -> dict | None:
    """Call Claude via the Agent SDK (supports OAuth login + API key)."""
    import os
    import shutil
    from claude_agent_sdk import query, ClaudeAgentOptions

    try:
        env = dict(os.environ)
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.claude_code_oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token

        options_kwargs = {
            "model": settings.default_model,
            "max_turns": 1,
            "allowed_tools": [],
            "env": env,
        }

        cli_path = shutil.which("claude")
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        options = ClaudeAgentOptions(**options_kwargs)

        full_response = ""
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result") and message.result is not None:
                full_response = message.result
            elif hasattr(message, "content"):
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        full_response += block.text

        if not full_response:
            logger.warning("Enrichment LLM returned no output")
            return None

        # Extract JSON from response — handle preamble, code fences, etc.
        text = full_response.strip()
        logger.debug(f"Enrichment raw response: {text[:500]}")

        # Try to find JSON object in the response
        # 1. Strip code fences
        if "```" in text:
            # Extract content between first ``` and last ```
            parts = text.split("```")
            for part in parts[1::2]:  # odd-indexed parts are inside fences
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{"):
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

        # 2. Find first { and last } — extract the JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        # 3. Try the whole thing as-is
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse enrichment response as JSON: {text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Enrichment LLM call failed: {e}")
        return None


async def _enrich_project(project_id: UUID, url: str):
    """Background task: fetch website and extract brand info via Haiku."""
    import httpx

    logger.info(f"Enriching project {project_id} from {url}")

    # Fetch website
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "MissionControl/1.0"})
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch {url}: HTTP {resp.status_code}")
            await _update_enrichment_status(project_id, "failed")
            return
        html = resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        await _update_enrichment_status(project_id, "failed")
        return

    # Extract text
    site_text = _strip_html_to_text(html)
    if len(site_text.strip()) < 50:
        logger.warning(f"Too little content from {url}")
        await _update_enrichment_status(project_id, "failed")
        return

    # Call Haiku
    brand_data = await _call_haiku(ENRICHMENT_PROMPT + site_text)
    if not brand_data:
        await _update_enrichment_status(project_id, "failed")
        return

    # Update project
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project:
            return

        meta = project.metadata_ or {}
        meta["brand"] = {
            "tagline": brand_data.get("tagline"),
            "offering": brand_data.get("offering"),
            "brand_voice": brand_data.get("brand_voice"),
            "tone_keywords": brand_data.get("tone_keywords") or [],
            "brand_colors": brand_data.get("brand_colors") or [],
        }
        meta["enrichment_status"] = "completed"
        project.metadata_ = meta

        # Auto-fill description if empty
        if not project.description and brand_data.get("offering"):
            project.description = brand_data["offering"]

        # Auto-set color from brand colors
        brand_colors = brand_data.get("brand_colors") or []
        if brand_colors and project.color == "#00ffc8":
            project.color = brand_colors[0]

        await db.commit()

    # Broadcast update so dashboard refreshes
    await broadcast("project.updated", {"project_id": str(project_id)})
    logger.info(f"Enrichment completed for project {project_id}")


async def _update_enrichment_status(project_id: UUID, status: str):
    """Update just the enrichment status in metadata."""
    async with async_session() as db:
        project = await db.get(Project, project_id)
        if not project:
            return
        meta = project.metadata_ or {}
        meta["enrichment_status"] = status
        project.metadata_ = meta
        await db.commit()
    await broadcast("project.updated", {"project_id": str(project_id)})


@router.post("/{project_id}/enrich")
async def enrich_project(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger brand enrichment for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.url:
        raise HTTPException(status_code=400, detail="Project has no URL to enrich from")

    # Set pending status
    meta = project.metadata_ or {}
    meta["enrichment_status"] = "pending"
    project.metadata_ = meta
    await db.flush()

    background_tasks.add_task(_enrich_project, project_id, project.url)
    return {"status": "enrichment_started", "project_id": str(project_id)}
