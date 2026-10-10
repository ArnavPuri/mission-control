"""
Shared Bot Command Handlers

Platform-agnostic command implementations. Each handler takes args and source,
performs the action, and returns a CommandResult.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.db.session import async_session
from app.db.models import (
    Task, Project, AgentConfig, Note,
    TaskStatus, AgentStatus, EventLog, AgentApproval, ApprovalStatus,
    BrandProfile, LEAD_TAG,
)
from app.orchestrator.runner import AgentRunner

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    text: str
    parse_mode: str | None = None


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
        agents_running = await db.scalar(
            select(func.count(AgentConfig.id)).where(AgentConfig.status == AgentStatus.RUNNING)
        )
        projects_active = await db.scalar(
            select(func.count(Project.id)).where(Project.status == "active")
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
        f"- Notes: {notes_count}",
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

    status_icons = {"active": "+", "planning": "~", "launched": "!", "paused": "-", "archived": "x"}
    lines = [
        f"[{status_icons.get(p.status.value, '?')}] {p.name} - {p.description[:60]}"
        for p in projects
    ]
    return CommandResult("Projects\n\n" + "\n".join(lines))


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
        return CommandResult("No brand profile configured yet.\nSet it up via the dashboard or API.")

    lines = [f"*{profile.name}*", ""]
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


def _time_ago(dt: datetime) -> str:
    seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    if seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    return f"{int(seconds / 86400)}d ago"


async def cmd_leads(args: str, source: str) -> CommandResult:
    """View open leads found by marketing agents (tasks tagged "lead")."""
    async with async_session() as db:
        result = await db.execute(
            select(Task)
            .where(Task.status != TaskStatus.DONE)
            .order_by(Task.created_at.desc())
            .limit(200)
        )
        leads = [t for t in result.scalars().all() if LEAD_TAG in (t.tags or [])][:5]

    if not leads:
        return CommandResult("No open leads.")

    lines = ["*Open Leads*", ""]
    for i, t in enumerate(leads, 1):
        lines.append(f"{i}. {t.text} ({t.priority.value})")
        meta = " · ".join(tag for tag in (t.tags or []) if tag != LEAD_TAG)
        lines.append(f"   {meta + ' · ' if meta else ''}{_time_ago(t.created_at)}")
        if t.url:
            lines.append(f"   {t.url}")
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
            time_str = _time_ago(a.last_run_at)

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
        "/note <title> - Create a note\n"
        "/approve [n] - List or approve pending actions\n"
        "/status - Dashboard stats\n"
        "/run <agent> - Trigger an agent\n"
        "/projects - List projects\n"
        "/leads — View open marketing leads\n"
        "/agents — View agent status\n"
        "/brand — View your brand profile\n"
        "/morning — Get your morning briefing\n"
        "/help - This message\n\n"
        "Or just send a message — I understand natural language."
    )
