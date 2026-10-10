"""
Shared Bot Command Handlers

Platform-agnostic command implementations. Each handler takes args and source,
performs the action, and returns a CommandResult.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.db.models import (
    Task, Project, AgentConfig, Note,
    TaskStatus, AgentStatus, EventLog, AgentApproval, ApprovalStatus,
    BrandProfile, LEAD_TAG,
)
from app.config import settings
from app.api.ws import broadcast
from app.integrations import github
from app.orchestrator import review, threads
from app.orchestrator.runner import start_background_run
from app.orchestrator.reminders import upcoming_reminders
from app.timeutil import aware, describe, end_of_day, local_tz, split_reminder

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    text: str
    parse_mode: str | None = None
    # Inline keyboard (Bot API reply_markup) for this message
    reply_markup: dict | None = None
    # Extra messages sent after this one, e.g. one per approval with its own buttons
    followups: list["CommandResult"] = field(default_factory=list)


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
    await broadcast("task.created", {"text": args, "source": source})

    return CommandResult(f"Task added: {args}")


async def cmd_note(args: str, source: str) -> CommandResult:
    """Create a note."""
    if not args:
        return CommandResult("Usage: /note <title>")

    async with async_session() as db:
        note = Note(title=args, content="", source=source)
        db.add(note)
        await db.commit()
    await broadcast("note.created", {"title": args, "source": source})

    return CommandResult(f"Note created: {args}")


REMIND_USAGE = (
    "Usage: /remind <when> <what>, e.g.\n"
    "/remind tomorrow at 9 call Sam\n"
    "/remind in 2h check the deploy\n"
    "/remind send invoice every monday 10am\n\n"
    "/remind on its own lists upcoming reminders."
)


async def create_reminder(db: AsyncSession, text: str, source: str) -> tuple[Task | None, str]:
    """Turn "tomorrow at 9 call Sam" into a task with a reminder. Returns the
    task (None if no time was found) and a confirmation."""
    when, what, recurrence = split_reminder(text)
    if not when or not what:
        return None, REMIND_USAGE
    task = Task(text=what, source=source, remind_at=when, due_date=end_of_day(when), recurrence=recurrence)
    db.add(task)
    db.add(EventLog(
        event_type="task.created", entity_type="task", source=source,
        data={"text": what, "remind_at": when.isoformat(), "recurrence": recurrence},
    ))
    await db.flush()
    repeat = f", then {recurrence}" if recurrence else ""
    return task, f"⏰ I'll remind you {describe(when)}{repeat}: {what}"


async def cmd_remind(args: str, source: str) -> CommandResult:
    """Add a task with a reminder, or list upcoming reminders."""
    async with async_session() as db:
        if not args.strip():
            upcoming = await upcoming_reminders(db)
            if not upcoming:
                return CommandResult(f"No reminders set.\n\n{REMIND_USAGE}")
            lines = ["*Upcoming reminders*", ""]
            lines += [f"• {describe(t.remind_at)} — {t.text[:80]}" + (" 🔁" if t.recurrence else "") for t in upcoming]
            return CommandResult("\n".join(lines))
        task, message = await create_reminder(db, args, source)
        if task:
            await db.commit()
    if task:
        await broadcast("task.created", {"id": str(task.id), "source": source})
    return CommandResult(message)


async def cmd_today(source: str) -> CommandResult:
    """What's overdue, due today and coming up."""
    now = datetime.now(timezone.utc)
    today_end = end_of_day(now)
    async with async_session() as db:
        result = await db.execute(
            select(Task).where(
                Task.status != TaskStatus.DONE,
                Task.due_date.isnot(None),
                Task.due_date <= today_end,
            ).order_by(Task.due_date)
        )
        due = result.scalars().all()
        later = [t for t in await upcoming_reminders(db) if aware(t.remind_at) <= today_end]

    overdue = [t for t in due if aware(t.due_date) < now]
    today = [t for t in due if aware(t.due_date) >= now]
    local_day = now.astimezone(local_tz()).strftime("%A %b %d").replace(" 0", " ")
    lines = [f"*Today — {local_day}*", ""]
    if overdue:
        lines.append(f"*Overdue ({len(overdue)})*")
        lines += [f"• {t.text[:80]} — was due {describe(t.due_date)}" for t in overdue[:10]]
        lines.append("")
    if today:
        lines.append(f"*Due today ({len(today)})*")
        lines += [f"• {t.text[:80]}" + (" 🔁" if t.recurrence else "") for t in today[:10]]
        lines.append("")
    if later:
        lines.append("*Reminders later today*")
        lines += [f"• {describe(t.remind_at)} — {t.text[:80]}" for t in later[:10]]
        lines.append("")
    if len(lines) == 2:
        lines.append("Nothing due today. 🎉")
    return CommandResult("\n".join(lines).strip())


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


async def find_agent(db: AsyncSession, query: str) -> tuple[AgentConfig | None, list[AgentConfig]]:
    """Match an agent by exact slug, then by name. Returns (agent, candidates) —
    agent is None when nothing or more than one agent matches."""
    query = query.strip()
    exact = (await db.execute(select(AgentConfig).where(AgentConfig.slug == query))).scalar_one_or_none()
    if exact:
        return exact, [exact]
    matches = (await db.execute(
        select(AgentConfig).where(
            (AgentConfig.slug.ilike(f"%{query}%")) | (AgentConfig.name.ilike(f"%{query}%"))
        ).order_by(AgentConfig.name)
    )).scalars().all()
    return (matches[0] if len(matches) == 1 else None), list(matches)


async def cmd_run(args: str, source: str) -> CommandResult:
    """Start an agent in the background; its result is sent when it finishes."""
    if not args:
        return CommandResult("Usage: /run <agent-name>")

    async with async_session() as db:
        agent, matches = await find_agent(db, args)
    if not agent:
        if not matches:
            return CommandResult(f"Agent not found: {args}")
        names = "\n".join(f"- {a.slug}" for a in matches)
        return CommandResult(f"Several agents match '{args}':\n{names}\n\nUse /run <slug>.")
    if agent.status == AgentStatus.DISABLED:
        return CommandResult(f"Agent {agent.name} is disabled")
    if not start_background_run(agent.id, trigger=source, notify=True):
        return CommandResult(f"Agent {agent.name} is already running")
    return CommandResult(f"Started {agent.name}. I'll message you when it's done.")


async def delegate(db: AsyncSession, agent: AgentConfig, request: str, source: str,
                   project: Project | None = None) -> tuple[Task, bool]:
    """Create a task from a request and assign it to an agent."""
    request = request.strip()
    title = request.split("\n", 1)[0]
    if len(title) > 120:
        title = title[:117] + "..."
    task = Task(
        text=title,
        description=request if request != title else None,
        source=source,
        project_id=project.id if project else None,
    )
    db.add(task)
    await db.flush()
    started = await threads.assign_task(db, task, agent, note=request)
    return task, started


async def cmd_ask(args: str, source: str) -> CommandResult:
    """Hand a task to an agent: /ask <agent> <what to do>."""
    parts = args.split(None, 1)
    if len(parts) < 2:
        return CommandResult("Usage: /ask <agent> <what you want done>\nExample: /ask navigator compare Plausible and Fathom pricing")

    async with async_session() as db:
        agent, matches = await find_agent(db, parts[0])
        if not agent:
            if not matches:
                return CommandResult(f"Agent not found: {parts[0]}. See /agents.")
            names = ", ".join(a.slug for a in matches)
            return CommandResult(f"Several agents match '{parts[0]}': {names}")
        if agent.status == AgentStatus.DISABLED:
            return CommandResult(f"Agent {agent.name} is disabled")
        task, started = await delegate(db, agent, parts[1], source)

    if started:
        return CommandResult(f"{agent.name} is on it: \"{task.text}\". You'll get the answer here.")
    return CommandResult(f"Queued for {agent.name} (busy right now): \"{task.text}\". You'll get the answer here.")


async def find_project(db: AsyncSession, words: list[str]) -> tuple[Project | None, int]:
    """Match a project name at the start of `words` (names may contain spaces).
    Returns the project and how many words its name used."""
    projects = (await db.execute(select(Project))).scalars().all()
    for n in range(len(words), 0, -1):
        candidate = " ".join(words[:n]).lower()
        exact = [p for p in projects if p.name.lower() == candidate]
        if exact:
            return exact[0], n
    first = words[0].lower() if words else ""
    partial = [p for p in projects if first and first in p.name.lower()]
    return (partial[0], 1) if len(partial) == 1 else (None, 0)


async def cmd_repo(args: str, source: str) -> CommandResult:
    """Link a project to its GitHub repo: /repo <project> <owner/repo>."""
    words = args.split()
    if len(words) < 2:
        return CommandResult("Usage: /repo <project> <owner/repo>")
    repo = github.normalize_repo(words[-1])
    if not repo:
        return CommandResult(f"'{words[-1]}' isn't a GitHub repo. Use owner/repo or a github.com URL.")
    async with async_session() as db:
        project, _ = await find_project(db, words[:-1])
        if not project:
            return CommandResult(f"Project not found: {' '.join(words[:-1])}. See /projects.")
        project.github_repo = repo
        await db.commit()
    return CommandResult(f"{project.name} → github.com/{repo}. Use /dev {project.name} <request> to hand it coding work.")


async def create_dev_task(db: AsyncSession, project: Project, request: str, source: str) -> tuple[Task, str]:
    request = request.strip()
    title = request.split("\n", 1)[0][:120]
    task = Task(text=title, description=request if request != title else None,
                source=source, project_id=project.id, tags=[github.DEV_TAG])
    db.add(task)
    await db.flush()
    url = await github.open_dev_issue(db, task, project)
    return task, url


async def cmd_dev(args: str, source: str) -> CommandResult:
    """Hand coding work to Claude Code via a GitHub issue: /dev <project> <request>."""
    if not github.configured():
        return CommandResult("GitHub isn't set up. Add GITHUB_TOKEN to .env and restart.")
    words = args.split()
    async with async_session() as db:
        project, used = await find_project(db, words)
        request = " ".join(words[used:])
        if not project or not request:
            return CommandResult("Usage: /dev <project> <what to build or fix>")
        try:
            task, url = await create_dev_task(db, project, request, source)
        except github.GitHubError as e:
            return CommandResult(f"Couldn't open the issue: {e}")
    lines = [f"Opened {url}"]
    if settings.github_mention_claude:
        lines.append("Claude Code will pick it up.")
    lines.append("I'll tell you when a PR shows up. Reply to my messages about it to comment on the issue.")
    return CommandResult("\n".join(lines))


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
    """List pending agent actions, each with Approve / Reject buttons."""
    async with async_session() as db:
        pending = await review.pending_approvals(db)
        messages = [review.approval_message(a, a.agent.name if a.agent else "Unknown") for a in pending]
        await db.commit()

    if not pending:
        return CommandResult("No pending approvals.")
    return CommandResult(
        f"{len(pending)} pending approval{'s' if len(pending) != 1 else ''}:",
        followups=[CommandResult(text, "Markdown", markup) for text, markup in messages],
    )


async def cmd_drafts(source: str) -> CommandResult:
    """Show the latest content drafts, each with Approve / Posted / Discard buttons."""
    async with async_session() as db:
        drafts = await review.pending_drafts(db)
    if not drafts:
        return CommandResult("No content drafts waiting.")
    messages = [review.draft_message(d) for d in drafts]
    return CommandResult(
        f"{len(drafts)} latest draft{'s' if len(drafts) != 1 else ''}:",
        followups=[CommandResult(text, "Markdown", markup) for text, markup in messages],
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
        "/remind <when> <what> - Set a reminder (e.g. /remind tomorrow 9am call Sam)\n"
        "/today - Overdue, due today, and today's reminders\n"
        "/note <title> - Create a note\n"
        "/approve - Review pending agent actions\n"
        "/drafts - Review content drafts\n"
        "/status - Dashboard stats\n"
        "/ask <agent> <request> - Hand a task to an agent\n"
        "/run <agent> - Run an agent's scheduled job now\n"
        "/dev <project> <request> - Hand coding work to Claude Code (GitHub issue)\n"
        "/repo <project> <owner/repo> - Link a project to its GitHub repo\n"
        "/projects - List projects\n"
        "/leads — View open marketing leads\n"
        "/agents — View agent status\n"
        "/brand — View your brand profile\n"
        "/morning — Get your morning briefing\n"
        "/help - This message\n\n"
        "Or just send a message — I understand natural language.\n"
        "Reply to an agent's message to continue that task's thread."
    )
