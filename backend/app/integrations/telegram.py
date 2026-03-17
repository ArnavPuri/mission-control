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
    TaskStatus, AgentStatus, EventLog, Habit, Goal, GoalStatus,
    JournalEntry, AgentApproval, ApprovalStatus,
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
        habits_active = await db.scalar(
            select(func.count(Habit.id)).where(Habit.is_active == True)
        )
        goals_active = await db.scalar(
            select(func.count(Goal.id)).where(Goal.status == GoalStatus.ACTIVE)
        )
        approvals_pending = await db.scalar(
            select(func.count(AgentApproval.id)).where(AgentApproval.status == ApprovalStatus.PENDING)
        )

    msg = (
        "📊 *Mission Control Status*\n\n"
        f"🔹 Projects: {projects_active} active\n"
        f"🔹 Tasks: {tasks_open} open\n"
        f"🔹 Ideas: {ideas_count}\n"
        f"🔹 Reading: {reading_count} unread\n"
        f"🔹 Habits: {habits_active} active\n"
        f"🔹 Goals: {goals_active} active\n"
        f"🔹 Agents: {agents_running} running"
    )
    if approvals_pending:
        msg += f"\n⏳ *{approvals_pending} pending approvals* — use /approve"
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


async def cmd_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Complete or create a habit."""
    if not is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""

    if not text:
        # List habits with streak info
        async with async_session() as db:
            result = await db.execute(select(Habit).where(Habit.is_active == True))
            habits = result.scalars().all()
        if not habits:
            await update.message.reply_text("No habits yet. Use /habit <name> to create one.")
            return
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date()
        lines = []
        for h in habits:
            done = any(c.completed_at.date() == today for c in (h.completions or []))
            icon = "✅" if done else "⬜"
            streak = f" 🔥{h.current_streak}" if h.current_streak > 0 else ""
            lines.append(f"{icon} *{h.name}*{streak}")
        await update.message.reply_text("↻ *Habits*\n\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # Check if it matches an existing habit to complete it
    async with async_session() as db:
        result = await db.execute(select(Habit).where(Habit.is_active == True))
        habits = result.scalars().all()
        match = next((h for h in habits if text.lower() in h.name.lower()), None)

        if match:
            from datetime import datetime, timezone, timedelta
            today = datetime.now(timezone.utc).date()
            already = any(c.completed_at.date() == today for c in (match.completions or []))
            if already:
                await update.message.reply_text(f"Already completed *{match.name}* today! 🎉", parse_mode="Markdown")
                return
            from app.db.models import HabitCompletion
            completion = HabitCompletion(habit_id=match.id)
            db.add(completion)
            yesterday = today - timedelta(days=1)
            had_yesterday = any(c.completed_at.date() == yesterday for c in (match.completions or []))
            if had_yesterday or match.current_streak == 0:
                match.current_streak += 1
            else:
                match.current_streak = 1
            match.best_streak = max(match.best_streak, match.current_streak)
            match.total_completions += 1
            await db.commit()
            await update.message.reply_text(
                f"✅ *{match.name}* completed! 🔥 Streak: {match.current_streak} days",
                parse_mode="Markdown",
            )
        else:
            # Create new habit
            habit = Habit(name=text, source="telegram")
            db.add(habit)
            await db.commit()
            await update.message.reply_text(f"↻ New habit created: *{text}*", parse_mode="Markdown")


async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""

    if not text:
        async with async_session() as db:
            result = await db.execute(select(Goal).where(Goal.status == GoalStatus.ACTIVE))
            goals = result.scalars().all()
        if not goals:
            await update.message.reply_text("No active goals. Use /goal <title> to create one.")
            return
        lines = []
        for g in goals:
            pct = round(g.progress * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"◎ *{g.title}*\n   {bar} {pct}%")
        await update.message.reply_text("◎ *Goals*\n\n" + "\n".join(lines), parse_mode="Markdown")
        return

    async with async_session() as db:
        goal = Goal(title=text)
        db.add(goal)
        await db.commit()
    await update.message.reply_text(f"◎ Goal created: *{text}*", parse_mode="Markdown")


async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""

    if not text:
        async with async_session() as db:
            result = await db.execute(
                select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(3)
            )
            entries = result.scalars().all()
        if not entries:
            await update.message.reply_text("No journal entries. Use /journal <text> to write one.")
            return
        lines = []
        mood_emoji = {"great": "✦", "good": "●", "okay": "○", "low": "◌", "bad": "×"}
        for e in entries:
            m = mood_emoji.get(e.mood.value, "·") if e.mood else "·"
            date = e.created_at.strftime("%b %d")
            lines.append(f"{m} *{date}* — {e.content[:80]}{'...' if len(e.content) > 80 else ''}")
        await update.message.reply_text("✎ *Journal*\n\n" + "\n".join(lines), parse_mode="Markdown")
        return

    async with async_session() as db:
        entry = JournalEntry(content=text, source="telegram")
        db.add(entry)
        await db.commit()
    await update.message.reply_text("✎ Journal entry saved.")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List and approve pending agent actions."""
    if not is_allowed(update.effective_user.id):
        return

    async with async_session() as db:
        result = await db.execute(
            select(AgentApproval).where(AgentApproval.status == ApprovalStatus.PENDING)
            .order_by(AgentApproval.created_at.desc())
        )
        pending = result.scalars().all()

    if not pending:
        await update.message.reply_text("No pending approvals. ✅")
        return

    arg = " ".join(context.args) if context.args else ""
    if arg:
        # Approve by index (1-based)
        try:
            idx = int(arg) - 1
            approval = pending[idx]
        except (ValueError, IndexError):
            await update.message.reply_text("Usage: /approve <number>")
            return
        async with async_session() as db:
            a = await db.get(AgentApproval, approval.id)
            from datetime import datetime, timezone
            a.status = ApprovalStatus.APPROVED
            a.reviewed_at = datetime.now(timezone.utc)
            agent = await db.get(AgentConfig, a.agent_id)
            if agent:
                runner = AgentRunner()
                await runner._process_actions(a.actions, agent, db)
            await db.commit()
        await update.message.reply_text(f"✅ Approved: {approval.summary[:200]}")
        return

    lines = []
    for i, a in enumerate(pending, 1):
        count = len(a.actions) if isinstance(a.actions, list) else 0
        lines.append(f"*{i}.* {a.agent.name if a.agent else 'Unknown'} — {count} actions\n   _{a.summary[:100]}_")
    await update.message.reply_text(
        "⏳ *Pending Approvals*\n\n" + "\n\n".join(lines) + "\n\nUse /approve <number> to approve.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 *Mission Control Commands*\n\n"
        "/task <text> — Add a task\n"
        "/idea <text> #tags — Capture an idea\n"
        "/read <title> [url] — Add to reading list\n"
        "/habit [name] — List habits or complete/create one\n"
        "/goal [title] — List goals or create one\n"
        "/journal [text] — View or write journal\n"
        "/approve [n] — List or approve pending actions\n"
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
    app.add_handler(CommandHandler("habit", cmd_habit))
    app.add_handler(CommandHandler("goal", cmd_goal))
    app.add_handler(CommandHandler("journal", cmd_journal))
    app.add_handler(CommandHandler("approve", cmd_approve))
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
        BotCommand("habit", "Complete or create a habit"),
        BotCommand("goal", "View or create goals"),
        BotCommand("journal", "Write a journal entry"),
        BotCommand("approve", "Review pending agent actions"),
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
