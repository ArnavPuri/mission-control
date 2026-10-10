"""Morning briefing — unified daily status sent to Telegram."""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import async_session
from app.db.models import (
    AgentRun, AgentRunStatus,
    MarketingContent, ContentStatus,
    Task, TaskStatus, TaskPriority,
    Project, ProjectStatus, LEAD_TAG,
)
from app.notifications.dispatcher import send_telegram
from app.timeutil import aware, describe, end_of_day, local_tz

logger = logging.getLogger(__name__)


async def generate_morning_briefing() -> str:
    """Generate the morning briefing text from live DB data."""
    now = datetime.now(timezone.utc)
    h12_ago = now - timedelta(hours=12)
    h24_ago = now - timedelta(hours=24)
    d7_ago = now - timedelta(days=7)

    async with async_session() as db:
        # --- Agent runs (last 12h) ---
        runs_result = await db.execute(
            select(AgentRun)
            .where(AgentRun.started_at >= h12_ago)
            .options(selectinload(AgentRun.agent))
        )
        recent_runs = runs_result.scalars().all()
        completed = sum(1 for r in recent_runs if r.status == AgentRunStatus.COMPLETED)
        failed_runs = [r for r in recent_runs if r.status == AgentRunStatus.FAILED]
        failed_count = len(failed_runs)

        # --- Leads (last 24h) ---
        recent_tasks_result = await db.execute(
            select(Task).where(Task.created_at >= h24_ago)
        )
        leads = [t for t in recent_tasks_result.scalars().all() if LEAD_TAG in (t.tags or [])]
        high_leads = [t for t in leads if t.priority in (TaskPriority.CRITICAL, TaskPriority.HIGH)]

        # --- Tasks ---
        high_tasks_result = await db.execute(
            select(func.count(Task.id)).where(
                Task.status != TaskStatus.DONE,
                Task.priority.in_([TaskPriority.CRITICAL, TaskPriority.HIGH]),
            )
        )
        high_task_count = high_tasks_result.scalar() or 0

        due_result = await db.execute(
            select(Task).where(
                Task.status != TaskStatus.DONE,
                Task.due_date.isnot(None),
                Task.due_date <= end_of_day(now),
            ).order_by(Task.due_date)
        )
        due_tasks = due_result.scalars().all()
        overdue_tasks = [t for t in due_tasks if aware(t.due_date) < now]
        due_today = [t for t in due_tasks if aware(t.due_date) >= now]

        # --- Projects ---
        projects_result = await db.execute(
            select(Project).where(Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.LAUNCHED]))
        )
        projects = projects_result.scalars().all()

        # Get counts per project
        project_stats = []
        for p in projects:
            task_count = await db.scalar(
                select(func.count(Task.id)).where(
                    Task.project_id == p.id, Task.status != TaskStatus.DONE
                )
            ) or 0
            lead_count = sum(1 for t in leads if t.project_id == p.id)
            project_stats.append((p.name, task_count, lead_count))

        # --- Content pipeline ---
        draft_count = await db.scalar(
            select(func.count(MarketingContent.id)).where(MarketingContent.status == ContentStatus.DRAFT)
        ) or 0
        posted_count = await db.scalar(
            select(func.count(MarketingContent.id)).where(
                MarketingContent.status == ContentStatus.POSTED,
                MarketingContent.posted_at >= d7_ago,
            )
        ) or 0

    # --- Format ---
    today = now.astimezone(local_tz()).strftime("%b %d")
    lines = [f"*Morning Briefing — {today}*", ""]

    # Today
    lines.append("*Today*")
    for t in due_today[:5]:
        lines.append(f"• {t.text[:60]}" + (" 🔁" if t.recurrence else ""))
    if len(due_today) > 5:
        lines.append(f"• …and {len(due_today) - 5} more due today")
    if overdue_tasks:
        lines.append(f"• ⚠️ {len(overdue_tasks)} overdue:")
        for t in overdue_tasks[:3]:
            lines.append(f"   – {t.text[:50]} (due {describe(t.due_date)})")
    if high_task_count:
        lines.append(f"• {high_task_count} critical/high tasks open")
    if not due_tasks and not high_task_count:
        lines.append("• All clear — nothing due")
    lines.append("")

    # Agents
    lines.append("*Agents (last 12h)*")
    if recent_runs:
        failed_names = ", ".join(set(
            r.agent.name if r.agent else "unknown" for r in failed_runs
        ))
        fail_part = f", {failed_count} failed ({failed_names})" if failed_count else ""
        lines.append(f"• {len(recent_runs)} ran: {completed} completed{fail_part}")
    else:
        lines.append("• No runs in last 12h")
    lines.append("")

    # Leads
    lines.append("*Leads (24h)*")
    if leads:
        lines.append(f"• {len(leads)} new leads, {len(high_leads)} high priority")
        for t in (high_leads or leads)[:3]:
            lines.append(f"• {t.text[:50]}")
    else:
        lines.append("• No new leads")
    lines.append("")

    # Products
    if project_stats:
        lines.append("*Products*")
        for name, tasks, project_leads in project_stats:
            lines.append(f"• {name}: {tasks} open tasks, {project_leads} new leads")
        lines.append("")

    # Content
    lines.append("*Content*")
    parts = []
    if draft_count:
        parts.append(f"{draft_count} drafts ready")
    if posted_count:
        parts.append(f"{posted_count} posted this week")
    if parts:
        lines.append(f"• {', '.join(parts)}")
    else:
        lines.append("• No content activity")
    lines.append("")

    lines.append("Use /today, /leads, /drafts, or /approve for details.")

    return "\n".join(lines)


async def send_morning_briefing() -> bool:
    """Generate and send the morning briefing to Telegram. Returns True if sent."""
    try:
        text = await generate_morning_briefing()
        sent = await send_telegram(text) is not None
        if sent:
            logger.info("Morning briefing sent")
        else:
            logger.warning("Morning briefing could not be sent (Telegram not configured)")
        return sent
    except Exception as e:
        logger.error(f"Morning briefing failed: {e}")
        return False
