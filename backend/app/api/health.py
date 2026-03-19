"""Health check API with detailed diagnostics per component."""

import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentRunStatus, AgentStatus, Task, EventLog

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check - verifies DB connection and LLM config."""
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        provider = settings.llm_provider.value
    except ValueError:
        provider = "not_configured"

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "llm_provider": provider,
        "telegram": "configured" if settings.telegram_bot_token else "not_configured",
    }


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed diagnostics for every component.

    Returns per-component status, latency, and diagnostic info.
    """
    components = {}
    overall_status = "ok"

    # 1. Database
    db_start = time.monotonic()
    try:
        result = await db.execute(text("SELECT 1"))
        db_latency = (time.monotonic() - db_start) * 1000
        # Check table count
        table_result = await db.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        table_count = table_result.scalar() or 0
        components["database"] = {
            "status": "ok",
            "latency_ms": round(db_latency, 1),
            "tables": table_count,
            "url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        }
    except Exception as e:
        db_latency = (time.monotonic() - db_start) * 1000
        overall_status = "degraded"
        components["database"] = {
            "status": "error",
            "latency_ms": round(db_latency, 1),
            "error": str(e)[:200],
        }

    # 2. LLM Provider
    try:
        provider = settings.llm_provider.value
        components["llm"] = {
            "status": "ok",
            "provider": provider,
            "default_model": settings.default_model,
            "smart_model": settings.smart_model,
            "max_budget_usd": settings.max_agent_budget_usd,
        }
    except ValueError as e:
        overall_status = "degraded"
        components["llm"] = {
            "status": "not_configured",
            "error": str(e)[:200],
        }

    # 3. Agents
    try:
        agent_result = await db.execute(select(AgentConfig))
        all_agents = agent_result.scalars().all()
        agent_counts = {"total": len(all_agents)}
        for status in AgentStatus:
            agent_counts[status.value] = sum(1 for a in all_agents if a.status == status)

        # Check for stuck agents (running for > 10 minutes)
        stuck_agents = [
            a.name for a in all_agents
            if a.status == AgentStatus.RUNNING and a.last_run_at
            and (datetime.now(timezone.utc) - a.last_run_at) > timedelta(minutes=10)
        ]

        # Recent failures
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        fail_result = await db.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.status == AgentRunStatus.FAILED,
                AgentRun.started_at >= one_hour_ago,
            )
        )
        recent_failures = fail_result.scalar() or 0

        agent_status = "ok"
        if stuck_agents:
            agent_status = "warning"
        if recent_failures > 5:
            agent_status = "degraded"

        components["agents"] = {
            "status": agent_status,
            "counts": agent_counts,
            "stuck_agents": stuck_agents,
            "recent_failures_1h": recent_failures,
        }
    except Exception as e:
        components["agents"] = {"status": "error", "error": str(e)[:200]}

    # 4. Skill files
    try:
        skills_dir = Path(settings.skills_dir)
        if skills_dir.exists():
            skill_files = list(skills_dir.glob("*.yaml")) + list(skills_dir.glob("*.yml"))
            components["skills"] = {
                "status": "ok",
                "directory": str(skills_dir),
                "file_count": len(skill_files),
                "files": [f.name for f in skill_files],
            }
        else:
            components["skills"] = {
                "status": "warning",
                "directory": str(skills_dir),
                "error": "Skills directory not found",
            }
    except Exception as e:
        components["skills"] = {"status": "error", "error": str(e)[:200]}

    # 5. Telegram
    components["telegram"] = {
        "status": "ok" if settings.telegram_bot_token else "not_configured",
        "configured": bool(settings.telegram_bot_token),
        "allowed_users": len(settings.telegram_allowed_user_ids),
    }

    # 6. Discord
    components["discord"] = {
        "status": "ok" if settings.discord_bot_token else "not_configured",
        "configured": bool(settings.discord_bot_token),
        "allowed_channels": len(settings.discord_channel_ids),
    }

    # 7. Data summary
    try:
        task_count = (await db.execute(select(func.count(Task.id)))).scalar() or 0
        event_count = (await db.execute(select(func.count(EventLog.id)))).scalar() or 0
        components["data"] = {
            "status": "ok",
            "task_count": task_count,
            "event_count": event_count,
        }
    except Exception as e:
        components["data"] = {"status": "error", "error": str(e)[:200]}

    # Overall
    if any(c.get("status") == "error" for c in components.values()):
        overall_status = "error"
    elif any(c.get("status") == "degraded" for c in components.values()):
        overall_status = "degraded"
    elif any(c.get("status") == "warning" for c in components.values()):
        overall_status = "warning"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
