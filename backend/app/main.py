"""
Mission Control - API Server

Telegram-first AI assistant with agents, memory, and scheduling.
Dashboard provides a simple overview and management UI.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import AuthMiddleware, router as auth_router
from app.config import settings
from app.db.session import init_db
from app.api import (
    projects, tasks, agents, ws, health, approvals, search,
    notifications, agent_memory, notes, marketing_content, brand, activity,
)
from app.orchestrator.scheduler import Scheduler
from app.orchestrator.runner import recover_interrupted_runs
from app.integrations.telegram import start_telegram_bot
from app.agents.skill_loader import sync_skills_to_db
from app.notifications.dispatcher import urgent_dispatch_loop, digest_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not settings.dashboard_password:
        logging.getLogger(__name__).warning(
            "DASHBOARD_PASSWORD is not set: the dashboard and API are open to anyone who can reach them"
        )
    await init_db()
    await recover_interrupted_runs()
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
# Added before CORS so CORS wraps it: 401s still carry CORS headers
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(health.router, tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(agent_memory.router, prefix="/api/agents", tags=["agent-memory"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(marketing_content.router, prefix="/api/mkt-content", tags=["marketing"])
app.include_router(brand.router, prefix="/api/brand-profile", tags=["brand"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(ws.router, tags=["websocket"])
