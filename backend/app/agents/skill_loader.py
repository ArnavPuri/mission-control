"""
Skill Loader

Reads agent skill YAML files from the skills/ directory and syncs
them to the database. Each YAML file defines one agent.

On startup, the loader:
  1. Scans the skills directory for *.yaml files
  2. Parses each file
  3. Upserts into the agent_configs table
  4. Disables agents whose skill files were removed
"""

import logging
import re
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AgentConfig, AgentStatus
from app.db.session import async_session

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """Convert agent name to filesystem-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def load_skill_file(path: Path) -> dict | None:
    """Parse a single skill YAML file."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data or not isinstance(data, dict):
            logger.warning(f"Skipping empty/invalid skill file: {path}")
            return None
        data["_source_file"] = str(path)
        return data
    except Exception as e:
        logger.error(f"Failed to parse skill file {path}: {e}")
        return None


async def sync_skills_to_db(skills_dir: str | None = None):
    """Scan skill files and upsert into database."""
    directory = Path(skills_dir or settings.skills_dir)
    if not directory.exists():
        logger.warning(f"Skills directory not found: {directory}")
        return

    skill_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    logger.info(f"Found {len(skill_files)} skill files in {directory}")

    loaded_slugs = set()

    async with async_session() as db:
        for path in skill_files:
            data = load_skill_file(path)
            if not data:
                continue

            name = data.get("name", path.stem)
            slug = slugify(name)
            loaded_slugs.add(slug)

            # Check if agent already exists
            result = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
            existing = result.scalar_one_or_none()

            agent_data = {
                "name": name,
                "slug": slug,
                "description": data.get("description", ""),
                "agent_type": data.get("type", "general"),
                "model": data.get("model", settings.default_model),
                "max_budget_usd": data.get("max_budget_usd", settings.max_agent_budget_usd),
                "prompt_template": data.get("prompt_template", ""),
                "tools": data.get("tools", []),
                "schedule_type": data.get("schedule", {}).get("type") if isinstance(data.get("schedule"), dict) else None,
                "schedule_value": data.get("schedule", {}).get("every") if isinstance(data.get("schedule"), dict) else None,
                "data_reads": data.get("data", {}).get("reads", []) if isinstance(data.get("data"), dict) else [],
                "data_writes": data.get("data", {}).get("writes", []) if isinstance(data.get("data"), dict) else [],
                "config": {k: v for k, v in data.items() if k not in (
                    "name", "description", "type", "model", "max_budget_usd",
                    "prompt_template", "tools", "schedule", "data", "_source_file",
                    "version", "requires_approval",
                )},
                "skill_file": str(path),
            }

            if existing:
                for key, val in agent_data.items():
                    setattr(existing, key, val)
                logger.info(f"Updated agent: {name}")
            else:
                agent = AgentConfig(**agent_data)
                db.add(agent)
                logger.info(f"Created agent: {name}")

        # Note: Only YAML-managed agents (skill_file IS NOT NULL) are synced.
        # Agents created via the UI (skill_file = NULL) are never touched by the loader.
        await db.commit()
    logger.info(f"Skill sync complete: {len(loaded_slugs)} agents loaded")
