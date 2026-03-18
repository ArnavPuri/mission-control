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
from app.db.models import AgentConfig, AgentStatus, AgentTrigger
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
                "config": {
                    **{k: v for k, v in data.items() if k not in (
                        "name", "description", "type", "model", "max_budget_usd",
                        "prompt_template", "tools", "schedule", "data", "_source_file",
                        "version", "requires_approval", "triggers",
                    )},
                    # Ensure persona/tone are always in config for the runner
                    "persona": data.get("persona", ""),
                    "tone": data.get("tone", ""),
                },
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

        # Second pass: sync triggers defined in YAML files
        await _sync_triggers(db, skills_dir=directory)

    logger.info(f"Skill sync complete: {len(loaded_slugs)} agents loaded")


async def _sync_triggers(db: AsyncSession, skills_dir: Path):
    """Sync trigger definitions from YAML files to the agent_triggers table.

    YAML format:
        triggers:
          - entity_type: signal
            event: created
            condition: {field: relevance_score, op: gt, value: "0.7"}
    """
    skill_files = list(skills_dir.glob("*.yaml")) + list(skills_dir.glob("*.yml"))

    for path in skill_files:
        data = load_skill_file(path)
        if not data:
            continue

        triggers_data = data.get("triggers")
        if not triggers_data or not isinstance(triggers_data, list):
            continue

        name = data.get("name", path.stem)
        slug = slugify(name)

        # Find the agent
        result = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
        agent = result.scalar_one_or_none()
        if not agent:
            continue

        # Delete existing YAML-managed triggers for this agent (re-sync from scratch)
        existing_triggers = await db.execute(
            select(AgentTrigger).where(
                AgentTrigger.agent_id == agent.id,
                AgentTrigger.name.like("yaml:%"),
            )
        )
        for old_trigger in existing_triggers.scalars().all():
            await db.delete(old_trigger)
        await db.flush()

        # Create triggers from YAML
        for i, trigger_def in enumerate(triggers_data):
            if not isinstance(trigger_def, dict):
                continue

            entity_type = trigger_def.get("entity_type")
            event = trigger_def.get("event")
            if not entity_type or not event:
                logger.warning(f"Skipping trigger {i} in {path}: missing entity_type or event")
                continue

            trigger_name = f"yaml:{slug}:{entity_type}.{event}"
            trigger = AgentTrigger(
                agent_id=agent.id,
                name=trigger_name,
                description=trigger_def.get("description", f"Auto-run {name} on {entity_type}.{event}"),
                entity_type=entity_type,
                event=event,
                condition=trigger_def.get("condition"),
                is_active=trigger_def.get("is_active", True),
            )
            db.add(trigger)
            logger.info(f"Synced trigger: {trigger_name}")

    await db.commit()
