"""
Telegram Bot Integration

Allows adding tasks, ideas, and reading items to Mission Control
directly from Telegram. Also supports checking status and triggering agents.

Commands:
  /task <text>         - Add a task
  /idea <text>         - Capture an idea
  /read <title> [url]  - Add to reading list
  /status              - Show current stats
  /run <agent-name>    - Trigger an agent manually
  /projects            - List projects
  /help                - Show commands
"""

import logging
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters,
)
from sqlalchemy import select, func

from app.config import settings
from app.db.session import async_session
from app.db.models import (
    Task, Idea, ReadingItem, Project, AgentConfig, AgentRun,
    TaskStatus, AgentStatus, EventLog,
)
from app.orchestrator.runner import AgentRunner
from app.integrations.chat import handle_chat

logger = logging.getLogger(__name__)


def is_allowed(user_id: int) -> bool:
    """Check if user is in the allowed list (empty = allow all)."""
    allowed = settings.telegram_allowed_user_ids
    return not allowed or user_id in allowed


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /task <description>")
        return

    async with async_session() as db:
        task = Task(text=text, source="telegram")
        db.add(task)
        event = EventLog(
            event_type="task.created",
            entity_type="task",
            source="telegram",
            data={"text": text},
        )
        db.add(event)
        await db.commit()

    await update.message.reply_text(f"✅ Task added: {text}")


async def cmd_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /idea <description>")
        return

    # Simple tag extraction: words starting with #
    tags = [w.lstrip("#") for w in text.split() if w.startswith("#")]
    clean_text = " ".join(w for w in text.split() if not w.startswith("#"))

    async with async_session() as db:
        idea = Idea(text=clean_text, tags=tags, source="telegram")
        db.add(idea)
        await db.commit()

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    await update.message.reply_text(f"💡 Idea captured: {clean_text}{tag_str}")


async def cmd_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /read <title> [url]")
        return

    # Check if last arg is a URL
    url = None
    if args[-1].startswith("http"):
        url = args[-1]
        title = " ".join(args[:-1])
    else:
        title = " ".join(args)

    if not title:
        title = url or "Untitled"

    async with async_session() as db:
        item = ReadingItem(title=title, url=url, source="telegram")
        db.add(item)
        await db.commit()

    await update.message.reply_text(f"📖 Added to reading list: {title}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    async with async_session() as db:
        tasks_open = await db.scalar(
            select(func.count(Task.id)).where(Task.status != TaskStatus.DONE)
        )
        ideas_count = await db.scalar(select(func.count(Idea.id)))
        reading_count = await db.scalar(
            select(func.count(ReadingItem.id)).where(ReadingItem.is_read == False)
        )
        agents_running = await db.scalar(
            select(func.count(AgentConfig.id)).where(AgentConfig.status == AgentStatus.RUNNING)
        )
        projects_active = await db.scalar(
            select(func.count(Project.id)).where(Project.status == "active")
        )

    msg = (
        "📊 *Mission Control Status*\n\n"
        f"🔹 Projects: {projects_active} active\n"
        f"🔹 Tasks: {tasks_open} open\n"
        f"🔹 Ideas: {ideas_count}\n"
        f"🔹 Reading: {reading_count} unread\n"
        f"🔹 Agents: {agents_running} running"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    agent_name = " ".join(context.args) if context.args else ""
    if not agent_name:
        await update.message.reply_text("Usage: /run <agent-name>")
        return

    async with async_session() as db:
        result = await db.execute(
            select(AgentConfig).where(
                (AgentConfig.slug == agent_name) | (AgentConfig.name.ilike(f"%{agent_name}%"))
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            await update.message.reply_text(f"❌ Agent not found: {agent_name}")
            return
        if agent.status == AgentStatus.RUNNING:
            await update.message.reply_text(f"⏳ Agent {agent.name} is already running")
            return

        await update.message.reply_text(f"🚀 Starting agent: {agent.name}...")
        runner = AgentRunner()
        run = await runner.start_run(agent, trigger="telegram", db=db)
        await db.commit()

    status_emoji = "✅" if run.status.value == "completed" else "❌"
    summary = run.output_data.get("summary", "No summary") if run.output_data else "No output"
    await update.message.reply_text(f"{status_emoji} {agent.name}: {summary[:500]}")


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    async with async_session() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = result.scalars().all()

    if not projects:
        await update.message.reply_text("No projects yet. Add one from the dashboard.")
        return

    status_icons = {"active": "🟢", "planning": "🟡", "paused": "🔴", "archived": "⚫"}
    lines = [f"{status_icons.get(p.status.value, '⚪')} *{p.name}* — {p.description[:60]}" for p in projects]
    await update.message.reply_text("📋 *Projects*\n\n" + "\n".join(lines), parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 *Mission Control Commands*\n\n"
        "/task <text> — Add a task\n"
        "/idea <text> #tags — Capture an idea\n"
        "/read <title> [url] — Add to reading list\n"
        "/status — Dashboard stats\n"
        "/run <agent> — Trigger an agent\n"
        "/projects — List projects\n"
        "/help — This message",
        parse_mode="Markdown",
    )


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages via the LLM chat assistant."""
    if not is_allowed(update.effective_user.id):
        return
    text = update.message.text.strip()
    if not text:
        return

    # Show typing indicator while processing
    await update.message.chat.send_action("typing")

    try:
        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)

        for reply in replies:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Chat handler error: {e}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I couldn't process that. Try a /command instead.\n"
            f"_Error: {str(e)[:100]}_",
            parse_mode="Markdown",
        )


async def start_telegram_bot():
    """Start the Telegram bot."""
    if not settings.telegram_bot_token:
        logger.info("Telegram bot not configured, skipping")
        return

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Register commands
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("idea", cmd_idea))
    app.add_handler(CommandHandler("read", cmd_read))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))

    # Set bot commands menu
    await app.bot.set_my_commands([
        BotCommand("task", "Add a task"),
        BotCommand("idea", "Capture an idea"),
        BotCommand("read", "Add to reading list"),
        BotCommand("status", "Dashboard stats"),
        BotCommand("run", "Trigger an agent"),
        BotCommand("projects", "List projects"),
        BotCommand("help", "Show commands"),
    ])

    logger.info("Telegram bot started")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep running
    try:
        while True:
            await __import__("asyncio").sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
