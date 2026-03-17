"""
Mission Control - API Server

Central API that the dashboard, telegram bot, and agents all talk to.
Real-time updates via WebSocket for the dashboard.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.api import projects, tasks, ideas, reading, agents, ws, health, habits, goals, journal, approvals, search
from app.orchestrator.scheduler import Scheduler
from app.integrations.telegram import start_telegram_bot
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

    yield

    # Shutdown
    scheduler_task.cancel()
    if telegram_task:
        telegram_task.cancel()


app = FastAPI(
    title="Mission Control",
    description="Personal AI-powered command center",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
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
app.include_router(ws.router, tags=["websocket"])
