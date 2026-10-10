"""
Task threads: assigning tasks to agents and talking to them about it.

A task assigned to an agent gets a thread of TaskComments. Whenever the
latest comment is from the user (the assignment itself, or a reply), it is
the agent's turn: the agent runs with the task and the thread, and posts
its answer back as a comment, which is also sent to Telegram. Replying to
that Telegram message adds the next user comment, and so on.

If the agent is busy when it's its turn, the scheduler picks the task up
as soon as the agent is free (see pending_assignments).
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentConfig, AgentRun, AgentStatus, EventLog, Task, TaskComment, TaskStatus,
)
from app.api.ws import broadcast
from app.notifications.dispatcher import send_telegram

logger = logging.getLogger(__name__)

USER = "user"
SYSTEM = "system"
THREAD_LIMIT = 20
TELEGRAM_REPLY_LIMIT = 3500


def agent_author(agent: AgentConfig) -> str:
    return f"agent:{agent.slug}"


async def load_thread(db: AsyncSession, task_id: UUID, limit: int = THREAD_LIMIT) -> list[TaskComment]:
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def assign_task(db: AsyncSession, task: Task, agent: AgentConfig, note: str | None = None) -> bool:
    """Assign a task to an agent and start it. Returns True if the agent started
    right away, False if it is busy (the scheduler starts it when it's free)."""
    task.assigned_agent_id = agent.id
    if task.status in (TaskStatus.TODO, TaskStatus.BLOCKED):
        task.status = TaskStatus.IN_PROGRESS
    db.add(TaskComment(task_id=task.id, author=USER, body=note or f"Assigned to {agent.name}"))
    db.add(EventLog(
        event_type="task.assigned", entity_type="task", entity_id=task.id,
        source="user", data={"agent": agent.slug},
    ))
    await db.commit()
    await broadcast("task.updated", {"id": str(task.id)})
    return _start(agent.id, task.id)


async def add_user_reply(
    db: AsyncSession, task: Task, body: str, telegram_message_id: int | None = None,
) -> AgentConfig | None:
    """Add a user comment. If an agent owns the task, it's the agent's turn again;
    returns that agent."""
    db.add(TaskComment(task_id=task.id, author=USER, body=body, telegram_message_id=telegram_message_id))
    agent = await db.get(AgentConfig, task.assigned_agent_id) if task.assigned_agent_id else None
    if agent and task.status in (TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.TODO):
        task.status = TaskStatus.IN_PROGRESS
        task.completed_at = None
    await db.commit()
    await broadcast("task.updated", {"id": str(task.id)})
    if agent:
        _start(agent.id, task.id)
    else:
        # Dev tasks live on GitHub: the reply goes to the issue as a comment
        from app.integrations import github
        try:
            await github.forward_reply(task, body)
        except github.GitHubError as e:
            logger.warning(f"Could not forward reply to GitHub: {e}")
    return agent


def _start(agent_id: UUID, task_id: UUID) -> bool:
    from app.orchestrator.runner import start_background_run
    return start_background_run(agent_id, trigger="task", task_id=task_id)


async def find_task_by_telegram_message(db: AsyncSession, message_id: int) -> Task | None:
    result = await db.execute(
        select(TaskComment).where(TaskComment.telegram_message_id == message_id).limit(1)
    )
    comment = result.scalar_one_or_none()
    return await db.get(Task, comment.task_id) if comment else None


async def pending_assignments(db: AsyncSession) -> list[tuple[UUID, UUID]]:
    """(agent_id, task_id) for assigned tasks where it's the agent's turn."""
    result = await db.execute(
        select(Task).where(Task.assigned_agent_id.isnot(None), Task.status != TaskStatus.DONE)
    )
    pending = []
    for task in result.scalars().all():
        agent = task.assigned_agent
        if not agent or agent.status == AgentStatus.DISABLED:
            continue
        thread = await load_thread(db, task.id, limit=1)
        if thread and thread[-1].author == USER:
            pending.append((agent.id, task.id))
    return pending


def assignment_prompt(agent: AgentConfig, task: Task, thread: list[TaskComment], context: dict) -> str:
    lines = [f"You have been assigned a task.\n\nTASK: {task.text}"]
    if task.description:
        lines.append(f"DETAILS: {task.description}")
    if task.url:
        lines.append(f"LINK: {task.url}")
    if task.project:
        lines.append(f"PROJECT: {task.project.name} — {task.project.description or ''}")

    if thread:
        lines.append("\nCONVERSATION SO FAR (oldest first):")
        for c in thread:
            who = "You" if c.author == agent_author(agent) else c.author
            lines.append(f"[{who}] {c.body}")

    lines.append("\nCONTEXT:\n" + json.dumps(context, indent=2, default=str))
    writes = ", ".join(agent.data_writes or []) or "nothing (reply only)"
    lines.append(f"""
Do the work now, using your tools where useful. If you can't finish without
an answer from the user, ask one clear question instead.

Respond with JSON only:
{{
  "summary": "one line on what you did",
  "reply": "your message to the user, in markdown. This IS the deliverable: the findings, the draft, the answer. Not a description of it.",
  "status": "done" if the task is complete, or "needs_input" if you asked a question,
  "actions": []
}}
"actions" is optional and uses the usual action types. You can write to: {writes}.""")
    return "\n".join(lines)


async def post_agent_reply(db: AsyncSession, task: Task, agent: AgentConfig, result: dict, run: AgentRun):
    """Record the agent's answer in the thread, update the task and tell the user."""
    reply = str(result.get("reply") or result.get("summary") or "(no reply)").strip()
    needs_input = str(result.get("status", "")).lower() in ("needs_input", "blocked", "question")
    if needs_input:
        task.status = TaskStatus.BLOCKED
    elif str(result.get("status", "done")).lower() == "done":
        task.status = TaskStatus.DONE
        task.completed_at = datetime.now(timezone.utc)

    comment = TaskComment(task_id=task.id, author=agent_author(agent), body=reply, run_id=run.id)
    db.add(comment)

    header = f"🤖 *{agent.name}* · {task.text[:80]}"
    footer = "_Reply to this message to answer._" if needs_input else "_Reply to this message to follow up._"
    body = reply if len(reply) <= TELEGRAM_REPLY_LIMIT else reply[:TELEGRAM_REPLY_LIMIT] + "\n\n… (full reply in the dashboard)"
    comment.telegram_message_id = await send_telegram(f"{header}\n\n{body}\n\n{footer}")


async def post_run_failure(db: AsyncSession, task_id: UUID, agent_name: str, error: str):
    task = await db.get(Task, task_id)
    if not task:
        return
    task.status = TaskStatus.BLOCKED
    text = f"{agent_name} couldn't finish this: {error[:300]}"
    comment = TaskComment(task_id=task_id, author=SYSTEM, body=text)
    db.add(comment)
    comment.telegram_message_id = await send_telegram(
        f"⚠️ {text}\n\nTask: {task.text[:80]}\nReply to this message to try again."
    )
