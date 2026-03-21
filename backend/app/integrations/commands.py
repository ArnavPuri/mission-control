"""
Shared Bot Command Handlers

Platform-agnostic command implementations used by both Telegram and Discord
(and any future bot adapters). Each handler takes a BotContext and args string,
performs the action, and returns a reply string.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.db.models import (
    Task, Idea, ReadingItem, Project, AgentConfig, AgentRun, Note,
    TaskStatus, AgentStatus, EventLog, Habit, HabitCompletion,
    Goal, GoalStatus, JournalEntry, AgentApproval, ApprovalStatus,
    BrandProfile,
)
from app.orchestrator.runner import AgentRunner

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a bot command execution."""
    text: str
    parse_mode: str | None = None  # "Markdown" for Telegram, None for plain


async def cmd_task(args: str, source: str) -> CommandResult:
    """Add a task."""
    if not args:
        return CommandResult("Usage: /task <description>")

    async with async_session() as db:
        task = Task(text=args, source=source)
        db.add(task)
        db.add(EventLog(
            event_type="task.created", entity_type="task",
            source=source, data={"text": args},
        ))
        await db.commit()

    return CommandResult(f"Task added: {args}")


async def cmd_idea(args: str, source: str) -> CommandResult:
    """Capture an idea with optional #tags."""
    if not args:
        return CommandResult("Usage: /idea <description>")

    tags = [w.lstrip("#") for w in args.split() if w.startswith("#")]
    clean_text = " ".join(w for w in args.split() if not w.startswith("#"))

    async with async_session() as db:
        idea = Idea(text=clean_text, tags=tags, source=source)
        db.add(idea)
        await db.commit()

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    return CommandResult(f"Idea captured: {clean_text}{tag_str}")


async def cmd_read(args: str, source: str) -> CommandResult:
    """Add to reading list."""
    if not args:
        return CommandResult("Usage: /read <title> [url]")

    words = args.split()
    url = None
    if words[-1].startswith("http"):
        url = words[-1]
        title = " ".join(words[:-1]) or url
    else:
        title = args

    async with async_session() as db:
        item = ReadingItem(title=title, url=url, source=source)
        db.add(item)
        await db.commit()

    return CommandResult(f"Added to reading list: {title}")


async def cmd_note(args: str, source: str) -> CommandResult:
    """Create a note."""
    if not args:
        return CommandResult("Usage: /note <title>")

    async with async_session() as db:
        note = Note(title=args, content="", source=source)
        db.add(note)
        await db.commit()

    return CommandResult(f"Note created: {args}")


async def cmd_status(source: str) -> CommandResult:
    """Show current stats."""
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
        notes_count = await db.scalar(select(func.count(Note.id)))
        approvals_pending = await db.scalar(
            select(func.count(AgentApproval.id)).where(AgentApproval.status == ApprovalStatus.PENDING)
        )

    from app.config import settings as _settings
    bot_name = _settings.bot_personality.get("name", "MC")
    lines = [
        f"{bot_name} Status",
        "",
        f"- Projects: {projects_active} active",
        f"- Tasks: {tasks_open} open",
        f"- Ideas: {ideas_count}",
        f"- Reading: {reading_count} unread",
        f"- Notes: {notes_count}",
        f"- Habits: {habits_active} active",
        f"- Goals: {goals_active} active",
        f"- Agents: {agents_running} running",
    ]
    if approvals_pending:
        lines.append(f"\n{approvals_pending} pending approvals")

    return CommandResult("\n".join(lines))


async def cmd_run(args: str, source: str) -> CommandResult:
    """Trigger an agent manually."""
    if not args:
        return CommandResult("Usage: /run <agent-name>")

    async with async_session() as db:
        result = await db.execute(
            select(AgentConfig).where(
                (AgentConfig.slug == args) | (AgentConfig.name.ilike(f"%{args}%"))
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return CommandResult(f"Agent not found: {args}")
        if agent.status == AgentStatus.RUNNING:
            return CommandResult(f"Agent {agent.name} is already running")

        runner = AgentRunner()
        run = await runner.start_run(agent, trigger=source, db=db)
        await db.commit()

    status_word = "Done" if run.status.value == "completed" else "Failed"
    summary = run.output_data.get("summary", "No summary") if run.output_data else "No output"
    return CommandResult(f"{status_word} - {agent.name}: {summary[:500]}")


async def cmd_projects(source: str) -> CommandResult:
    """List projects."""
    async with async_session() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = result.scalars().all()

    if not projects:
        return CommandResult("No projects yet. Add one from the dashboard.")

    status_icons = {"active": "+", "planning": "~", "paused": "-", "archived": "x"}
    lines = [
        f"[{status_icons.get(p.status.value, '?')}] {p.name} - {p.description[:60]}"
        for p in projects
    ]
    return CommandResult("Projects\n\n" + "\n".join(lines))


async def cmd_habit(args: str, source: str) -> CommandResult:
    """Complete or create a habit, or list all habits."""
    if not args:
        async with async_session() as db:
            result = await db.execute(select(Habit).where(Habit.is_active == True))
            habits = result.scalars().all()
        if not habits:
            return CommandResult("No habits yet. Use /habit <name> to create one.")

        today = datetime.now(timezone.utc).date()
        lines = []
        for h in habits:
            done = any(c.completed_at.date() == today for c in (h.completions or []))
            icon = "[x]" if done else "[ ]"
            streak = f" streak:{h.current_streak}" if h.current_streak > 0 else ""
            lines.append(f"{icon} {h.name}{streak}")
        return CommandResult("Habits\n\n" + "\n".join(lines))

    async with async_session() as db:
        result = await db.execute(select(Habit).where(Habit.is_active == True))
        habits = result.scalars().all()
        match = next((h for h in habits if args.lower() in h.name.lower()), None)

        if match:
            today = datetime.now(timezone.utc).date()
            already = any(c.completed_at.date() == today for c in (match.completions or []))
            if already:
                return CommandResult(f"Already completed {match.name} today!")

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
            return CommandResult(f"{match.name} completed! Streak: {match.current_streak} days")
        else:
            habit = Habit(name=args, source=source)
            db.add(habit)
            await db.commit()
            return CommandResult(f"New habit created: {args}")


async def cmd_goal(args: str, source: str) -> CommandResult:
    """List goals or create one."""
    if not args:
        async with async_session() as db:
            result = await db.execute(select(Goal).where(Goal.status == GoalStatus.ACTIVE))
            goals = result.scalars().all()
        if not goals:
            return CommandResult("No active goals. Use /goal <title> to create one.")
        lines = []
        for g in goals:
            pct = round(g.progress * 100)
            lines.append(f"- {g.title} ({pct}%)")
        return CommandResult("Goals\n\n" + "\n".join(lines))

    async with async_session() as db:
        goal = Goal(title=args)
        db.add(goal)
        await db.commit()
    return CommandResult(f"Goal created: {args}")


async def cmd_journal(args: str, source: str) -> CommandResult:
    """View recent journal or write an entry."""
    if not args:
        async with async_session() as db:
            result = await db.execute(
                select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(3)
            )
            entries = result.scalars().all()
        if not entries:
            return CommandResult("No journal entries. Use /journal <text> to write one.")
        lines = []
        for e in entries:
            date = e.created_at.strftime("%b %d")
            mood = f" ({e.mood.value})" if e.mood else ""
            lines.append(f"- {date}{mood}: {e.content[:80]}{'...' if len(e.content) > 80 else ''}")
        return CommandResult("Journal\n\n" + "\n".join(lines))

    async with async_session() as db:
        entry = JournalEntry(content=args, source=source)
        db.add(entry)
        await db.commit()
    return CommandResult("Journal entry saved.")


async def cmd_approve(args: str, source: str) -> CommandResult:
    """List and approve pending agent actions."""
    async with async_session() as db:
        result = await db.execute(
            select(AgentApproval).where(AgentApproval.status == ApprovalStatus.PENDING)
            .order_by(AgentApproval.created_at.desc())
        )
        pending = result.scalars().all()

    if not pending:
        return CommandResult("No pending approvals.")

    if args:
        try:
            idx = int(args) - 1
            approval = pending[idx]
        except (ValueError, IndexError):
            return CommandResult("Usage: /approve <number>")

        async with async_session() as db:
            a = await db.get(AgentApproval, approval.id)
            a.status = ApprovalStatus.APPROVED
            a.reviewed_at = datetime.now(timezone.utc)
            agent = await db.get(AgentConfig, a.agent_id)
            if agent:
                runner = AgentRunner()
                await runner._process_actions(a.actions, agent, db)
            await db.commit()
        return CommandResult(f"Approved: {approval.summary[:200]}")

    lines = []
    for i, a in enumerate(pending, 1):
        count = len(a.actions) if isinstance(a.actions, list) else 0
        agent_name = a.agent.name if a.agent else "Unknown"
        lines.append(f"{i}. {agent_name} - {count} actions: {a.summary[:100]}")
    return CommandResult(
        "Pending Approvals\n\n" + "\n\n".join(lines) + "\n\nUse /approve <number> to approve."
    )


async def cmd_brand(source: str) -> CommandResult:
    """Show current brand profile."""
    async with async_session() as db:
        result = await db.execute(select(BrandProfile).limit(1))
        profile = result.scalar_one_or_none()

    if not profile or not profile.name:
        return CommandResult("No brand profile configured yet.\nSet it up via the API: PUT /api/brand-profile")

    lines = [
        f"*{profile.name}*",
        "",
    ]
    if profile.bio:
        lines.append(profile.bio)
        lines.append("")
    if profile.tone:
        lines.append(f"Tone: {profile.tone}")
    if profile.topics:
        lines.append(f"Topics: {', '.join(profile.topics)}")
    if profile.talking_points:
        for product, points in profile.talking_points.items():
            lines.append(f"{product}: {', '.join(points)}")
    if profile.avoid:
        lines.append(f"Avoid: {', '.join(profile.avoid)}")

    return CommandResult("\n".join(lines))


async def cmd_signals(args: str, source: str) -> CommandResult:
    """View recent marketing signals."""
    from app.db.models import MarketingSignal, SignalStatus

    async with async_session() as db:
        query = select(MarketingSignal).order_by(MarketingSignal.created_at.desc()).limit(5)

        status_filter = args.strip().lower() if args.strip() else "new"
        if status_filter != "all":
            status_map = {"new": "new", "reviewed": "reviewed", "dismissed": "dismissed", "acted_on": "acted_on"}
            if status_filter in status_map:
                query = query.where(MarketingSignal.status == SignalStatus(status_map[status_filter]))

        result = await db.execute(query)
        signals = result.scalars().all()

    if not signals:
        return CommandResult(f"No {status_filter} signals found.")

    lines = [f"*Recent Signals* ({status_filter})", ""]
    for i, s in enumerate(signals, 1):
        score = int((s.relevance_score or 0) * 100)
        ago = datetime.now(timezone.utc) - s.created_at
        if ago.total_seconds() < 3600:
            time_str = f"{int(ago.total_seconds() / 60)}m ago"
        elif ago.total_seconds() < 86400:
            time_str = f"{int(ago.total_seconds() / 3600)}h ago"
        else:
            time_str = f"{int(ago.total_seconds() / 86400)}d ago"

        lines.append(f"{i}. {s.title} ({score}%)")
        lines.append(f"   {s.source_type} · {s.signal_type} · {time_str}")
        lines.append("")

    return CommandResult("\n".join(lines))


async def cmd_agents_list(source: str) -> CommandResult:
    """View agent status."""
    async with async_session() as db:
        result = await db.execute(select(AgentConfig).order_by(AgentConfig.name))
        agents = result.scalars().all()

    if not agents:
        return CommandResult("No agents configured.")

    emoji = {AgentStatus.IDLE: "🟢", AgentStatus.RUNNING: "🟡", AgentStatus.ERROR: "🔴", AgentStatus.DISABLED: "⚪"}
    lines = ["*Agents*", ""]

    for a in agents:
        e = emoji.get(a.status, "⚪")
        line = f"{e} {a.name} — {a.status.value}"
        lines.append(line)

        if a.last_run_at:
            ago = datetime.now(timezone.utc) - a.last_run_at
            if ago.total_seconds() < 3600:
                time_str = f"{int(ago.total_seconds() / 60)}m ago"
            elif ago.total_seconds() < 86400:
                time_str = f"{int(ago.total_seconds() / 3600)}h ago"
            else:
                time_str = f"{int(ago.total_seconds() / 86400)}d ago"

            latest_run = a.runs[0] if a.runs else None
            if latest_run:
                cost_str = f" · ${latest_run.cost_usd:.3f}" if latest_run.cost_usd else ""
                lines.append(f"   Last run: {time_str} · {latest_run.status.value}{cost_str}")
            else:
                lines.append(f"   Last run: {time_str}")
        lines.append("")

    return CommandResult("\n".join(lines))


async def cmd_morning(source: str) -> CommandResult:
    """Generate and send the morning briefing."""
    from app.notifications.morning import generate_morning_briefing
    text = await generate_morning_briefing()
    return CommandResult(text)


async def cmd_help(source: str) -> CommandResult:
    """Show available commands."""
    from app.config import settings
    bot_name = settings.bot_personality.get("name", "MC")
    return CommandResult(
        f"{bot_name} Commands\n\n"
        "/task <text> - Add a task\n"
        "/idea <text> #tags - Capture an idea\n"
        "/read <title> [url] - Add to reading list\n"
        "/note <title> - Create a note\n"
        "/habit [name] - List habits or complete/create one\n"
        "/goal [title] - List goals or create one\n"
        "/journal [text] - View or write journal\n"
        "/approve [n] - List or approve pending actions\n"
        "/status - Dashboard stats\n"
        "/run <agent> - Trigger an agent\n"
        "/projects - List projects\n"
        "/signals [status] — View marketing signals\n"
        "/agents — View agent status\n"
        "/brand — View your brand profile\n"
        "/morning — Get your morning briefing\n"
        "/help - This message"
    )
