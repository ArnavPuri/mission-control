"""Agent Marketplace — browse, search, install, and rate agent skill files.

Provides a gallery of available agents with categories, ratings, and one-click installation.
"""

import logging
from pathlib import Path
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from sqlalchemy import func as sqlfunc, case

from app.config import settings
from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentRunStatus
from app.agents.skill_loader import load_skill_file, slugify, sync_skills_to_db

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Category definitions ---

AGENT_CATEGORIES = {
    "productivity": {
        "name": "Productivity",
        "description": "Task management, planning, and daily workflows",
        "icon": "clipboard-list",
    },
    "marketing": {
        "name": "Marketing",
        "description": "Content, social media, and growth agents",
        "icon": "megaphone",
    },
    "research": {
        "name": "Research",
        "description": "Web research, data analysis, and competitive intelligence",
        "icon": "search",
    },
    "engineering": {
        "name": "Engineering",
        "description": "Code review, CI/CD, and development workflows",
        "icon": "code",
    },
    "health": {
        "name": "Health & Wellness",
        "description": "Wellness tracking, fitness, and mental health",
        "icon": "heart",
    },
    "finance": {
        "name": "Finance",
        "description": "Budget tracking, revenue alerts, and financial planning",
        "icon": "dollar-sign",
    },
    "learning": {
        "name": "Learning",
        "description": "Study plans, resource curation, and skill development",
        "icon": "book-open",
    },
    "general": {
        "name": "General",
        "description": "Multi-purpose and utility agents",
        "icon": "bot",
    },
}


class AgentRating(BaseModel):
    agent_id: str
    rating: int  # 1-5
    comment: str = ""


class AgentInstall(BaseModel):
    skill_file: str  # filename in skills directory


# --- Gallery endpoints ---

@router.get("/categories")
async def list_categories():
    """List all agent categories."""
    return [{"id": k, **v} for k, v in AGENT_CATEGORIES.items()]


@router.get("/gallery")
async def agent_gallery(
    category: str | None = None,
    search: str | None = None,
    installed_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Browse the agent gallery with filtering and search.

    Returns all available skill files and their installation status.
    """
    skills_dir = Path(settings.skills_dir)
    if not skills_dir.exists():
        return []

    # Load all skill files
    skill_files = list(skills_dir.glob("*.yaml")) + list(skills_dir.glob("*.yml"))

    # Get installed agents from DB
    result = await db.execute(select(AgentConfig))
    installed = {a.slug: a for a in result.scalars().all()}

    # Pre-fetch run stats for all agents in a single query (avoids N+1)
    agent_ids = [a.id for a in installed.values()]
    run_stats_map: dict[str, dict] = {}
    if agent_ids:
        stats_query = (
            select(
                AgentRun.agent_id,
                sqlfunc.count(AgentRun.id).label("total"),
                sqlfunc.sum(case(
                    (AgentRun.status == AgentRunStatus.COMPLETED, 1),
                    else_=0,
                )).label("successes"),
                sqlfunc.coalesce(sqlfunc.sum(AgentRun.cost_usd), 0).label("total_cost"),
            )
            .where(AgentRun.agent_id.in_(agent_ids))
            .group_by(AgentRun.agent_id)
        )
        stats_result = await db.execute(stats_query)
        for row in stats_result.all():
            aid, total, successes, total_cost = row
            run_stats_map[str(aid)] = {
                "total_runs": total,
                "success_rate": round((successes or 0) / total, 2) if total > 0 else 0,
                "total_cost_usd": round(float(total_cost or 0), 4),
            }

    gallery = []
    for path in skill_files:
        if path.name.startswith("_"):  # skip templates
            continue

        data = load_skill_file(path)
        if not data:
            continue

        name = data.get("name", path.stem)
        slug = slugify(name)
        agent_type = data.get("type", "general")
        db_agent = installed.get(slug)

        # Category filter
        if category and agent_type != category:
            continue

        # Search filter
        if search:
            search_lower = search.lower()
            searchable = f"{name} {data.get('description', '')} {data.get('persona', '')}".lower()
            if search_lower not in searchable:
                continue

        # Installed filter
        is_installed = slug in installed
        if installed_only and not is_installed:
            continue

        # Get run stats from pre-fetched map
        stats = run_stats_map.get(str(db_agent.id)) if db_agent else None

        # Read rating from config
        rating_data = (db_agent.config or {}).get("_rating") if db_agent else None

        gallery.append({
            "slug": slug,
            "name": name,
            "description": data.get("description", ""),
            "category": agent_type,
            "category_info": AGENT_CATEGORIES.get(agent_type, AGENT_CATEGORIES["general"]),
            "model": data.get("model", settings.default_model),
            "max_budget_usd": data.get("max_budget_usd", settings.max_agent_budget_usd),
            "schedule": data.get("schedule"),
            "version": data.get("version", "1.0"),
            "persona": data.get("persona", ""),
            "is_installed": is_installed,
            "agent_id": str(db_agent.id) if db_agent else None,
            "skill_file": path.name,
            "stats": stats,
            "rating": rating_data,
            "has_triggers": bool(data.get("triggers")),
            "requires_approval": data.get("requires_approval", False),
            "tools": data.get("tools", []),
        })

    # Sort: installed first, then by name
    gallery.sort(key=lambda x: (not x["is_installed"], x["name"]))
    return gallery


@router.post("/install")
async def install_agent(data: AgentInstall, db: AsyncSession = Depends(get_db)):
    """Install an agent from the skills directory by re-syncing skill files."""
    skills_dir = Path(settings.skills_dir).resolve()
    skill_path = (skills_dir / data.skill_file).resolve()
    if not skill_path.is_relative_to(skills_dir):
        raise HTTPException(status_code=400, detail="Invalid skill file path")
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill file not found: {data.skill_file}")

    # Re-sync all skills (installs any new ones)
    await sync_skills_to_db(str(skills_dir))

    # Find the newly installed agent
    skill_data = load_skill_file(skill_path)
    if skill_data:
        slug = slugify(skill_data.get("name", skill_path.stem))
        result = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
        agent = result.scalar_one_or_none()
        if agent:
            return {"installed": True, "agent_id": str(agent.id), "name": agent.name}

    return {"installed": True, "message": "Skills synced"}


@router.post("/rate")
async def rate_agent(data: AgentRating, db: AsyncSession = Depends(get_db)):
    """Rate an installed agent (1-5 stars)."""
    try:
        agent_uuid = UUID(data.agent_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid agent_id format")
    agent = await db.get(AgentConfig, agent_uuid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    config = dict(agent.config or {})
    config["_rating"] = {"score": data.rating, "comment": data.comment}
    agent.config = config
    await db.flush()

    return {"rated": True, "agent_name": agent.name, "rating": data.rating}


@router.get("/stats")
async def marketplace_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate marketplace statistics."""
    skills_dir = Path(settings.skills_dir)
    skill_files = list(skills_dir.glob("*.yaml")) + list(skills_dir.glob("*.yml"))
    total_available = sum(1 for f in skill_files if not f.name.startswith("_"))

    result = await db.execute(select(AgentConfig))
    agents = result.scalars().all()

    # Category breakdown
    categories = {}
    for a in agents:
        cat = a.agent_type or "general"
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_available": total_available,
        "total_installed": len(agents),
        "categories": categories,
    }
