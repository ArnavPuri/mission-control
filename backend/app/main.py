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
from app.api import (
    projects, tasks, ideas, agents, ws, health, approvals, search,
    webhooks, export, notifications, agent_memory, triggers,
    agent_analytics, autotag, notes, api_keys, github_integration,
    rss_feeds, marketing_signals, marketing_content, marketing_stats,
    routines, dedup, workflows, smart_priority, push, backup,
    user_patterns, webhook_templates, rate_limit, agent_versions,
    agent_marketplace, pipeline_builder, ab_testing, agent_budget,
    email_ingest, zapier, linear_integration, notion_integration,
    todoist_integration, plugins, brand,
)
from app.orchestrator.scheduler import Scheduler
from app.integrations.telegram import start_telegram_bot
from app.integrations.discord_bot import start_discord_bot
from app.integrations.slack_bot import start_slack_bot
from app.integrations.email_ingest import start_email_poller
from app.agents.skill_loader import sync_skills_to_db
from app.plugins.loader import plugin_manager
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

    # Start Slack bot if configured
    slack_task = None
    if settings.slack_bot_token and settings.slack_app_token:
        slack_task = asyncio.create_task(start_slack_bot())

    # Load plugins
    plugin_manager.load_plugins()

    # Start email IMAP poller if configured
    email_task = None
    if settings.email_imap_host and settings.email_imap_user:
        email_task = asyncio.create_task(start_email_poller())

    # Retry stuck enrichments (pending from prior restart)
    asyncio.create_task(_retry_stuck_enrichments())

    # Start notification dispatcher
    urgent_dispatch_task = asyncio.create_task(urgent_dispatch_loop())
    digest_dispatch_task = asyncio.create_task(digest_loop())

    yield

    # Shutdown
    scheduler_task.cancel()
    if telegram_task:
        telegram_task.cancel()
    if discord_task:
        discord_task.cancel()
    if slack_task:
        slack_task.cancel()
    if email_task:
        email_task.cancel()
    urgent_dispatch_task.cancel()
    digest_dispatch_task.cancel()


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

# Rate limiting middleware
from app.api.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Mount route modules
app.include_router(health.router, tags=["health"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(ideas.router, prefix="/api/ideas", tags=["ideas"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
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
app.include_router(marketing_stats.router, prefix="/api/mkt-stats", tags=["marketing"])
app.include_router(routines.router, prefix="/api/routines", tags=["routines"])
app.include_router(dedup.router, prefix="/api/dedup", tags=["dedup"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(smart_priority.router, prefix="/api/priority", tags=["priority"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(user_patterns.router, prefix="/api/patterns", tags=["patterns"])
app.include_router(webhook_templates.router, prefix="/api/webhooks/templates", tags=["webhook-templates"])
app.include_router(rate_limit.router, prefix="/api/rate-limit", tags=["rate-limit"])
app.include_router(agent_versions.router, prefix="/api/agents", tags=["agent-versions"])
app.include_router(agent_marketplace.router, prefix="/api/marketplace", tags=["marketplace"])
app.include_router(pipeline_builder.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(ab_testing.router, prefix="/api/ab-tests", tags=["ab-testing"])
app.include_router(agent_budget.router, prefix="/api/budget", tags=["budget"])
app.include_router(email_ingest.router, prefix="/api/email", tags=["email"])
app.include_router(zapier.router, prefix="/api/zapier", tags=["zapier"])
app.include_router(linear_integration.router, prefix="/api/linear", tags=["linear"])
app.include_router(notion_integration.router, prefix="/api/notion", tags=["notion"])
app.include_router(todoist_integration.router, prefix="/api/todoist", tags=["todoist"])
app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
app.include_router(brand.router, prefix="/api/brand-profile", tags=["brand"])
app.include_router(ws.router, tags=["websocket"])
