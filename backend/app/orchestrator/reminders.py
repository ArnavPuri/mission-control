"""
Reminders, due dates and recurring tasks.

A task's remind_at is when to ping you on Telegram. The scheduler sends due
reminders every minute with Done / Snooze buttons and records reminded_at.
A recurring task stays one task until you complete it; completing it
creates the next one, with its due date and reminder moved one step on.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import EventLog, Task, TaskComment, TaskStatus
from app.notifications.dispatcher import send_telegram
from app.timeutil import DEFAULT_HOUR, RECURRENCES, aware, describe, local_tz, next_occurrence

logger = logging.getLogger(__name__)

# Telegram callback_data prefix: "rem:<verb>:<task id>"
REMINDER_CB = "rem"
SYSTEM = "system"

# A reminder Telegram keeps rejecting is dropped after this many tries
MAX_SEND_ATTEMPTS = 5
_send_failures: dict[UUID, int] = {}


def _next_after(dt: datetime | None, recurrence: str, now: datetime) -> datetime | None:
    """The next occurrence after now; a task completed late skips the missed ones."""
    if dt is None:
        return None
    nxt = next_occurrence(dt, recurrence)
    while nxt <= now:
        nxt = next_occurrence(nxt, recurrence)
    return nxt


async def complete_task(db: AsyncSession, task: Task, source: str = "user") -> Task | None:
    """Mark a task done. For a recurring task, create the next one and return it."""
    now = datetime.now(timezone.utc)
    task.status = TaskStatus.DONE
    task.completed_at = task.completed_at or now
    if task.recurrence not in RECURRENCES:
        return None

    # The series moves to the new task, so reopening and completing this one
    # again doesn't create a second copy
    recurrence, task.recurrence = task.recurrence, None
    due, remind = aware(task.due_date), aware(task.remind_at)
    next_due = _next_after(due, recurrence, now)
    if remind and due:
        # Keep the reminder's offset from the due date ("9am on the day it's due")
        next_remind = next_due - (due - remind)
    else:
        next_remind = _next_after(remind, recurrence, now)

    nxt = Task(
        text=task.text, description=task.description, url=task.url,
        priority=task.priority, project_id=task.project_id, tags=list(task.tags or []),
        source=task.source, recurrence=recurrence, due_date=next_due, remind_at=next_remind,
    )
    db.add(nxt)
    await db.flush()
    db.add(EventLog(
        event_type="task.recurred", entity_type="task", entity_id=nxt.id, source=source,
        data={"from": str(task.id), "recurrence": recurrence},
    ))
    return nxt


def set_reminder(task: Task, when: datetime | None):
    task.remind_at = when
    task.reminded_at = None


async def due_reminders(db: AsyncSession, now: datetime) -> list[Task]:
    result = await db.execute(
        select(Task).where(
            Task.status != TaskStatus.DONE,
            Task.remind_at.isnot(None),
            Task.remind_at <= now,
            or_(Task.reminded_at.is_(None), Task.reminded_at < Task.remind_at),
        ).order_by(Task.remind_at)
    )
    return list(result.scalars().all())


async def upcoming_reminders(db: AsyncSession, limit: int = 15) -> list[Task]:
    result = await db.execute(
        select(Task).where(
            Task.status != TaskStatus.DONE,
            Task.remind_at.isnot(None),
            or_(Task.reminded_at.is_(None), Task.reminded_at < Task.remind_at),
        ).order_by(Task.remind_at).limit(limit)
    )
    return list(result.scalars().all())


def task_details(task: Task) -> str:
    """"due tomorrow · Launch · 🔁 weekly" (empty if there's nothing to say)."""
    parts = []
    if task.due_date:
        parts.append(f"due {describe(task.due_date)}")
    if task.project:
        parts.append(task.project.name)
    if task.recurrence:
        parts.append(f"🔁 {task.recurrence}")
    return " · ".join(parts)


def reminder_message(task: Task) -> tuple[str, dict]:
    details = task_details(task)
    text = f"⏰ *{task.text[:200]}*" + (f"\n{details}" if details else "")
    if task.description:
        text += f"\n\n{task.description[:500]}"
    markup = {"inline_keyboard": [[
        {"text": "✅ Done", "callback_data": f"{REMINDER_CB}:done:{task.id}"},
        {"text": "⏰ 1 hour", "callback_data": f"{REMINDER_CB}:1h:{task.id}"},
        {"text": "📅 Tomorrow", "callback_data": f"{REMINDER_CB}:tmr:{task.id}"},
    ]]}
    return text, markup


async def send_due_reminders(db: AsyncSession, now: datetime | None = None) -> int:
    """Send every reminder that is due. Returns how many were sent."""
    if not (settings.telegram_bot_token and settings.telegram_target_chat_id):
        return 0
    now = now or datetime.now(timezone.utc)
    sent = 0
    for task in await due_reminders(db, now):
        text, markup = reminder_message(task)
        message_id = await send_telegram(text, reply_markup=markup)
        if message_id is None:
            failures = _send_failures[task.id] = _send_failures.get(task.id, 0) + 1
            if failures < MAX_SEND_ATTEMPTS:
                continue
            logger.error(f"Giving up on the reminder for task {task.id} after {failures} attempts")
        _send_failures.pop(task.id, None)
        task.reminded_at = now
        if message_id is not None:
            sent += 1
            # Replying to the reminder on Telegram adds to the task's thread
            db.add(TaskComment(task_id=task.id, author=SYSTEM, body="⏰ Reminder sent",
                               telegram_message_id=message_id))
    return sent


def tomorrow_morning(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(timezone.utc)).astimezone(local_tz())
    day = local.date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, DEFAULT_HOUR, tzinfo=local_tz())


async def handle_callback(db: AsyncSession, verb: str, task_id: UUID) -> str:
    """A tap on a reminder's button."""
    task = await db.get(Task, task_id)
    if not task:
        return "That task no longer exists."
    now = datetime.now(timezone.utc)
    if verb == "done":
        if task.status == TaskStatus.DONE:
            return "Already done."
        nxt = await complete_task(db, task, source="telegram")
        if nxt:
            when = nxt.remind_at or nxt.due_date
            return f"✅ Done. Next: {describe(when)}" if when else "✅ Done"
        return "✅ Done"
    if verb in ("1h", "tmr"):
        when = now + timedelta(hours=1) if verb == "1h" else tomorrow_morning(now)
        set_reminder(task, when)
        return f"⏰ Snoozed until {describe(when)}"
    return "Unknown button."
