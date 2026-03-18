"""
Discord Bot Integration

Mirrors Telegram bot functionality: add tasks, ideas, reading items,
check status, and trigger agents via Discord.

Commands:
  !task <text>         - Add a task
  !idea <text>         - Capture an idea
  !read <title> [url]  - Add to reading list
  !note <title>        - Create a note
  !status              - Show current stats
  !run <agent-name>    - Trigger an agent manually
  !help                - Show commands

Requires DISCORD_BOT_TOKEN in .env
"""

import logging
from sqlalchemy import select, func

from app.config import settings
from app.db.session import async_session
from app.db.models import (
    Task, Idea, ReadingItem, Project, AgentConfig, AgentRun,
    TaskStatus, AgentStatus, EventLog, Habit, Goal, GoalStatus,
    JournalEntry, Note,
)
from app.orchestrator.runner import AgentRunner

logger = logging.getLogger(__name__)


async def start_discord_bot():
    """Start the Discord bot."""
    if not settings.discord_bot_token:
        logger.info("Discord bot not configured, skipping")
        return

    try:
        import discord
    except ImportError:
        logger.warning("discord.py not installed — pip install discord.py")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    allowed_channels = settings.discord_channel_ids

    def is_allowed(channel_id: int) -> bool:
        return not allowed_channels or channel_id in allowed_channels

    @client.event
    async def on_ready():
        logger.info(f"Discord bot connected as {client.user}")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        if not is_allowed(message.channel.id):
            return

        content = message.content.strip()
        if not content.startswith("!"):
            return

        parts = content.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "!task":
            if not args:
                await message.reply("Usage: `!task <description>`")
                return
            async with async_session() as db:
                task = Task(text=args, source="discord")
                db.add(task)
                db.add(EventLog(
                    event_type="task.created", entity_type="task",
                    source="discord", data={"text": args},
                ))
                await db.commit()
            await message.reply(f"Task added: {args}")

        elif cmd == "!idea":
            if not args:
                await message.reply("Usage: `!idea <description>`")
                return
            tags = [w.lstrip("#") for w in args.split() if w.startswith("#")]
            clean = " ".join(w for w in args.split() if not w.startswith("#"))
            async with async_session() as db:
                idea = Idea(text=clean, tags=tags, source="discord")
                db.add(idea)
                await db.commit()
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            await message.reply(f"Idea captured: {clean}{tag_str}")

        elif cmd == "!read":
            if not args:
                await message.reply("Usage: `!read <title> [url]`")
                return
            words = args.split()
            url = None
            if words[-1].startswith("http"):
                url = words[-1]
                title = " ".join(words[:-1]) or url
            else:
                title = args
            async with async_session() as db:
                item = ReadingItem(title=title, url=url, source="discord")
                db.add(item)
                await db.commit()
            await message.reply(f"Added to reading list: {title}")

        elif cmd == "!note":
            if not args:
                await message.reply("Usage: `!note <title>`")
                return
            async with async_session() as db:
                note = Note(title=args, content="", source="discord")
                db.add(note)
                await db.commit()
            await message.reply(f"Note created: {args}")

        elif cmd == "!status":
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
                habits_active = await db.scalar(
                    select(func.count(Habit.id)).where(Habit.is_active == True)
                )
                goals_active = await db.scalar(
                    select(func.count(Goal.id)).where(Goal.status == GoalStatus.ACTIVE)
                )
                notes_count = await db.scalar(select(func.count(Note.id)))

            msg = (
                "**Mission Control Status**\n"
                f"- Tasks: {tasks_open} open\n"
                f"- Ideas: {ideas_count}\n"
                f"- Reading: {reading_count} unread\n"
                f"- Notes: {notes_count}\n"
                f"- Habits: {habits_active} active\n"
                f"- Goals: {goals_active} active\n"
                f"- Agents: {agents_running} running"
            )
            await message.reply(msg)

        elif cmd == "!run":
            if not args:
                await message.reply("Usage: `!run <agent-name>`")
                return
            async with async_session() as db:
                result = await db.execute(
                    select(AgentConfig).where(
                        (AgentConfig.slug == args) | (AgentConfig.name.ilike(f"%{args}%"))
                    )
                )
                agent = result.scalar_one_or_none()
                if not agent:
                    await message.reply(f"Agent not found: {args}")
                    return
                if agent.status == AgentStatus.RUNNING:
                    await message.reply(f"Agent {agent.name} is already running")
                    return

                await message.reply(f"Starting agent: {agent.name}...")
                runner = AgentRunner()
                run = await runner.start_run(agent, trigger="discord", db=db)
                await db.commit()

            summary = run.output_data.get("summary", "No summary") if run.output_data else "No output"
            status = "Done" if run.status.value == "completed" else "Failed"
            await message.reply(f"**{status}** — {agent.name}: {summary[:500]}")

        elif cmd == "!help":
            await message.reply(
                "**Mission Control Commands**\n"
                "`!task <text>` — Add a task\n"
                "`!idea <text> #tags` — Capture an idea\n"
                "`!read <title> [url]` — Add to reading list\n"
                "`!note <title>` — Create a note\n"
                "`!status` — Dashboard stats\n"
                "`!run <agent>` — Trigger an agent\n"
                "`!help` — This message"
            )

    logger.info("Starting Discord bot...")
    await client.start(settings.discord_bot_token)
