"""
Mission Control - API Server

Telegram-first AI assistant with agents, memory, and scheduling.
Dashboard provides a simple overview and management UI.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.api import (
    projects, tasks, agents, ws, health, approvals, search,
    notifications, agent_memory, notes, marketing_signals,
    marketing_content, brand,
)
from app.orchestrator.scheduler import Scheduler
from app.integrations.telegram import start_telegram_bot
from app.agents.skill_loader import sync_skills_to_db
from app.notifications.dispatcher import urgent_dispatch_loop, digest_loop


async def _retry_stuck_enrichments():
    """Retry any project enrichments stuck in 'pending' from a prior restart."""
    import logging
    from sqlalchemy import select
    from app.db.session import async_session
    from app.db.models import Project
    from app.api.projects import _enrich_project

    logger = logging.getLogger(__name__)
    await asyncio.sleep(5)  # let startup settle
    try:
        async with async_session() as db:
            result = await db.execute(select(Project).where(Project.url.isnot(None)))
            for project in result.scalars().all():
                meta = project.metadata_ or {}
                if meta.get("enrichment_status") == "pending":
                    logger.info(f"Retrying stuck enrichment for {project.name}")
                    asyncio.create_task(_enrich_project(project.id, project.url))
    except Exception as e:
        logger.warning(f"Failed to retry stuck enrichments: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await sync_skills_to_db()

    # Start scheduler
    scheduler = Scheduler()
    scheduler_task = asyncio.create_task(scheduler.run())

    # Start Telegram bot
    telegram_task = None
    if settings.telegram_bot_token:
        telegram_task = asyncio.create_task(start_telegram_bot())

    # Start notification dispatcher
    urgent_dispatch_task = asyncio.create_task(urgent_dispatch_loop())
    digest_dispatch_task = asyncio.create_task(digest_loop())

    yield

    # Shutdown
    scheduler_task.cancel()
    if telegram_task:
        telegram_task.cancel()
    urgent_dispatch_task.cancel()
    digest_dispatch_task.cancel()


app = FastAPI(
    title="Mission Control",
    description="Telegram-first AI assistant with agents and scheduling",
    version="0.7.0",
    lifespan=lifespan,
)

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(health.router, tags=["health"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(agent_memory.router, prefix="/api/agents", tags=["agent-memory"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(marketing_signals.router, prefix="/api/mkt-signals", tags=["marketing"])
app.include_router(marketing_content.router, prefix="/api/mkt-content", tags=["marketing"])
app.include_router(brand.router, prefix="/api/brand-profile", tags=["brand"])
app.include_router(ws.router, tags=["websocket"])
