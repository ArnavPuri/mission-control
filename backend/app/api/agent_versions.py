"""Agent Versioning API.

Tracks changes to agent skill files over time, storing snapshots of
YAML config whenever agents are synced from disk.
"""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig
from app.agents.skill_loader import load_skill_file

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory version store (persisted as JSON in agent config)
# Each version: {version, hash, timestamp, changes, snapshot}


class AgentVersion(BaseModel):
    version: int
    hash: str
    timestamp: str
    changes: list[str]
    snapshot: dict


def _hash_config(data: dict) -> str:
    """Compute a content hash for an agent config dict."""
    # Exclude volatile fields
    stable = {k: v for k, v in sorted(data.items())
              if k not in ("_source_file", "last_run_at", "status", "updated_at", "created_at")}
    content = str(stable).encode()
    return hashlib.sha256(content).hexdigest()[:16]


def _detect_changes(old: dict, new: dict) -> list[str]:
    """Detect what changed between two config snapshots."""
    changes = []
    ignore_keys = {"_source_file", "updated_at", "created_at", "last_run_at", "status"}

    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys - ignore_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            if old_val is None:
                changes.append(f"Added {key}")
            elif new_val is None:
                changes.append(f"Removed {key}")
            elif key == "prompt_template":
                old_len = len(str(old_val))
                new_len = len(str(new_val))
                changes.append(f"Modified prompt_template ({old_len} -> {new_len} chars)")
            else:
                changes.append(f"Changed {key}: {str(old_val)[:50]} -> {str(new_val)[:50]}")

    return changes


def _get_versions(agent: AgentConfig) -> list[dict]:
    """Get version history from agent config."""
    config = agent.config or {}
    return config.get("_versions", [])


def _save_versions(agent: AgentConfig, versions: list[dict]):
    """Save version history to agent config."""
    config = dict(agent.config or {})
    config["_versions"] = versions
    agent.config = config


@router.get("/{agent_id}/versions")
async def list_versions(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """List all tracked versions of an agent's configuration."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = _get_versions(agent)
    return {
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "total_versions": len(versions),
        "versions": [
            {
                "version": v["version"],
                "hash": v["hash"],
                "timestamp": v["timestamp"],
                "changes": v["changes"],
            }
            for v in versions
        ],
    }


@router.get("/{agent_id}/versions/{version}")
async def get_version(agent_id: UUID, version: int, db: AsyncSession = Depends(get_db)):
    """Get a specific version's full snapshot."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = _get_versions(agent)
    for v in versions:
        if v["version"] == version:
            return v
    raise HTTPException(status_code=404, detail=f"Version {version} not found")


@router.get("/{agent_id}/versions/{v1}/diff/{v2}")
async def diff_versions(agent_id: UUID, v1: int, v2: int, db: AsyncSession = Depends(get_db)):
    """Compare two versions of an agent configuration."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = _get_versions(agent)
    ver1 = next((v for v in versions if v["version"] == v1), None)
    ver2 = next((v for v in versions if v["version"] == v2), None)

    if not ver1 or not ver2:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    changes = _detect_changes(ver1.get("snapshot", {}), ver2.get("snapshot", {}))
    return {
        "agent_id": str(agent.id),
        "from_version": v1,
        "to_version": v2,
        "changes": changes,
    }


@router.post("/{agent_id}/snapshot")
async def create_snapshot(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually create a version snapshot of the current agent configuration."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    snapshot = _build_snapshot(agent)
    content_hash = _hash_config(snapshot)

    versions = _get_versions(agent)

    # Check if anything changed
    if versions and versions[-1]["hash"] == content_hash:
        return {"message": "No changes detected", "current_version": versions[-1]["version"]}

    # Detect changes from last version
    changes = []
    if versions:
        changes = _detect_changes(versions[-1].get("snapshot", {}), snapshot)

    new_version = {
        "version": len(versions) + 1,
        "hash": content_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "changes": changes or ["Initial snapshot"],
        "snapshot": snapshot,
    }

    versions.append(new_version)
    # Keep last 50 versions
    if len(versions) > 50:
        versions = versions[-50:]

    _save_versions(agent, versions)
    await db.flush()

    return {
        "version": new_version["version"],
        "hash": content_hash,
        "changes": new_version["changes"],
    }


def _build_snapshot(agent: AgentConfig) -> dict:
    """Build a snapshot dict from current agent state."""
    return {
        "name": agent.name,
        "description": agent.description,
        "agent_type": agent.agent_type,
        "model": agent.model,
        "max_budget_usd": agent.max_budget_usd,
        "prompt_template": agent.prompt_template,
        "tools": agent.tools or [],
        "schedule_type": agent.schedule_type,
        "schedule_value": agent.schedule_value,
        "data_reads": agent.data_reads or [],
        "data_writes": agent.data_writes or [],
        "config": {k: v for k, v in (agent.config or {}).items() if not k.startswith("_")},
        "skill_file": agent.skill_file,
    }


async def auto_snapshot_on_sync(agent: AgentConfig, db: AsyncSession):
    """Called during skill sync to automatically track version changes.

    Should be called after updating agent fields from YAML.
    """
    snapshot = _build_snapshot(agent)
    content_hash = _hash_config(snapshot)

    versions = _get_versions(agent)

    # Skip if no change
    if versions and versions[-1]["hash"] == content_hash:
        return

    changes = []
    if versions:
        changes = _detect_changes(versions[-1].get("snapshot", {}), snapshot)

    new_version = {
        "version": len(versions) + 1,
        "hash": content_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "changes": changes or ["Initial snapshot"],
        "snapshot": snapshot,
    }

    versions.append(new_version)
    if len(versions) > 50:
        versions = versions[-50:]

    _save_versions(agent, versions)
    logger.info(f"Agent {agent.name}: version {new_version['version']} (changes: {changes})")
