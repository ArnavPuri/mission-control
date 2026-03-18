"""
Mission Control - API Server

Central API that the dashboard, telegram bot, and agents all talk to.
Real-time updates via WebSocket for the dashboard.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.api import projects, tasks, ideas, reading, agents, ws, health, habits, goals, journal, approvals, search, webhooks, export, notifications, agent_memory, triggers, agent_analytics, autotag, notes, api_keys, github_integration, rss_feeds, marketing_signals, marketing_content
from app.orchestrator.scheduler import Scheduler
from app.integrations.telegram import start_telegram_bot
from app.integrations.discord_bot import start_discord_bot
from app.agents.skill_loader import sync_skills_to_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Sync skill YAML files to database
    await sync_skills_to_db()

    # Start the agent scheduler
    scheduler = Scheduler()
    scheduler_task = asyncio.create_task(scheduler.run())

    # Start Telegram bot if configured
    telegram_task = None
    if settings.telegram_bot_token:
        telegram_task = asyncio.create_task(start_telegram_bot())

    # Start Discord bot if configured
    discord_task = None
    if settings.discord_bot_token:
        discord_task = asyncio.create_task(start_discord_bot())

    yield

    # Shutdown
    scheduler_task.cancel()
    if telegram_task:
        telegram_task.cancel()
    if discord_task:
        discord_task.cancel()


app = FastAPI(
    title="Mission Control",
    description="Personal AI-powered command center",
    version="0.1.0",
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
app.include_router(ideas.router, prefix="/api/ideas", tags=["ideas"])
app.include_router(reading.router, prefix="/api/reading", tags=["reading"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(habits.router, prefix="/api/habits", tags=["habits"])
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(agent_memory.router, prefix="/api/agents", tags=["agent-memory"])
app.include_router(triggers.router, prefix="/api/triggers", tags=["triggers"])
app.include_router(agent_analytics.router, prefix="/api/analytics/agents", tags=["analytics"])
app.include_router(autotag.router, prefix="/api/autotag", tags=["autotag"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(api_keys.router, prefix="/api/keys", tags=["api-keys"])
app.include_router(github_integration.router, prefix="/api/github", tags=["github"])
app.include_router(rss_feeds.router, prefix="/api/feeds", tags=["feeds"])
app.include_router(marketing_signals.router, prefix="/api/mkt-signals", tags=["marketing"])
app.include_router(marketing_content.router, prefix="/api/mkt-content", tags=["marketing"])
app.include_router(ws.router, tags=["websocket"])
