"""
Agent-to-agent handoffs.

An agent can pass work to a teammate with a "handoff" action, e.g. Pulse
finds a lead and asks Echo to draft a reply:

    {"type": "handoff", "agent": "echo", "request": "Draft a reply to ...", "task_id": "<lead>"}

The handoff becomes a new task assigned to the teammate, linked to the task
it came from (parent_task_id). The teammate's answer goes to its own thread
and to Telegram as usual, and the parent's thread notes the outcome.

Chains are bounded: a handoff can't go deeper than MAX_DEPTH tasks, and one
run can hand off at most MAX_PER_RUN times.
"""

import logging
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentConfig, AgentStatus, EventLog, Task, TaskComment, TaskStatus
from app.orchestrator.coordinator import has_open_handoffs, is_coordinator

logger = logging.getLogger(__name__)

MAX_DEPTH = 3
MAX_PER_RUN = 3
SYSTEM = "system"


async def teammates(db: AsyncSession, agent: AgentConfig) -> list[dict]:
    """The other agents this one can hand work to."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.id != agent.id, AgentConfig.status != AgentStatus.DISABLED)
        .order_by(AgentConfig.name)
    )
    return [
        {"slug": a.slug, "name": a.name, "does": (a.description or "")[:160]}
        for a in result.scalars().all()
    ]


async def _find(db: AsyncSession, query: str) -> AgentConfig | None:
    query = (query or "").strip()
    if not query:
        return None
    exact = (await db.execute(select(AgentConfig).where(AgentConfig.slug == query))).scalar_one_or_none()
    if exact:
        return exact
    matches = (await db.execute(
        select(AgentConfig).where(AgentConfig.slug.ilike(f"%{query}%") | AgentConfig.name.ilike(f"%{query}%"))
    )).scalars().all()
    return matches[0] if len(matches) == 1 else None


async def depth(db: AsyncSession, task: Task) -> int:
    """1 for a task nobody handed off, 2 for its handoff, and so on."""
    level, seen = 1, {task.id}
    while task.parent_task_id and level <= MAX_DEPTH:
        task = await db.get(Task, task.parent_task_id)
        if not task or task.id in seen:
            break
        seen.add(task.id)
        level += 1
    return level


def _start_after_commit(db: AsyncSession, agent_id: UUID, task_id: UUID):
    """Start the teammate once the new task is committed (its run reads it in its own session)."""
    @event.listens_for(db.sync_session, "after_commit", once=True)
    def _start(_session):
        from app.orchestrator.runner import start_background_run
        # If the teammate is busy, the scheduler starts it when it's free
        start_background_run(agent_id, trigger="handoff", task_id=task_id)


async def hand_off(db: AsyncSession, from_agent: AgentConfig, action: dict) -> Task:
    """Create the teammate's task. Raises ValueError when the handoff isn't allowed."""
    request = (action.get("request") or action.get("text") or "").strip()
    if not request:
        raise ValueError("handoff needs a request")
    target = await _find(db, action.get("agent") or "")
    if not target:
        raise ValueError(f"no agent matches '{action.get('agent')}'")
    if target.id == from_agent.id:
        raise ValueError("an agent can't hand off to itself")
    if target.status == AgentStatus.DISABLED:
        raise ValueError(f"{target.name} is disabled")

    parent = None
    if action.get("task_id"):
        try:
            parent = await db.get(Task, UUID(str(action["task_id"])))
        except ValueError:
            parent = None
    if parent and await depth(db, parent) >= MAX_DEPTH:
        raise ValueError(f"handoff chain is already {MAX_DEPTH} tasks deep")

    title, _, details = request.partition("\n")
    task = Task(
        text=title if len(title) <= 200 else title[:197] + "…",
        description=details.strip() or None,
        status=TaskStatus.IN_PROGRESS,
        assigned_agent_id=target.id,
        parent_task_id=parent.id if parent else None,
        project_id=(parent.project_id if parent else None) or from_agent.project_id or target.project_id,
        source=f"agent:{from_agent.slug}",
    )
    db.add(task)
    await db.flush()
    # The request is the first message in the teammate's thread: its turn to answer
    db.add(TaskComment(task_id=task.id, author=f"agent:{from_agent.slug}", body=request))
    if parent:
        db.add(TaskComment(task_id=parent.id, author=SYSTEM, body=f"↪ {from_agent.name} handed “{task.text}” to {target.name}"))
    db.add(EventLog(
        event_type="task.handoff", entity_type="task", entity_id=task.id, source=f"agent:{from_agent.slug}",
        data={"to": target.slug, "parent": str(parent.id) if parent else None},
    ))
    _start_after_commit(db, target.id, task.id)
    logger.info(f"{from_agent.name} handed “{task.text}” to {target.name}")
    return task


async def handed_by(db: AsyncSession, task: Task, agent: AgentConfig) -> str | None:
    """Slug of the teammate who handed this task to agent (its thread starts with their request)."""
    first = (await db.execute(
        select(TaskComment.author).where(TaskComment.task_id == task.id)
        .order_by(TaskComment.created_at).limit(1)
    )).scalar_one_or_none()
    if first and first.startswith("agent:") and first != f"agent:{agent.slug}":
        return first.removeprefix("agent:")
    return None


async def report_to_parent(db: AsyncSession, task: Task, agent: AgentConfig, needs_input: bool,
                           reply: str = "") -> Task | None:
    """Pass a handed-off task's outcome back to the thread it came from.

    A coordinator gets the teammate's whole reply, and its turn back once all
    the work it handed out has settled. Anyone else gets a one-line note.
    """
    if not task.parent_task_id:
        return None
    parent = await db.get(Task, task.parent_task_id)
    if not parent:
        return None
    owner = await db.get(AgentConfig, parent.assigned_agent_id) if parent.assigned_agent_id else None
    if is_coordinator(owner):
        state = "asks about" if needs_input else "finished"
        db.add(TaskComment(
            task_id=parent.id, author=f"agent:{agent.slug}",
            body=f"**{agent.name}** {state} “{task.text}”:\n\n{reply}",
        ))
        await db.flush()
        if parent.status != TaskStatus.DONE and not await has_open_handoffs(db, parent):
            _start_after_commit(db, owner.id, parent.id)
        return parent
    outcome = "is waiting on you for" if needs_input else "finished"
    db.add(TaskComment(task_id=parent.id, author=SYSTEM, body=f"↪ {agent.name} {outcome} “{task.text}”"))
    return parent


async def follow_up(db: AsyncSession, from_agent: AgentConfig, action: dict) -> Task:
    """Send more to a teammate working on a task you handed out (an answer to
    its question, or a change of plan). It's the teammate's turn again."""
    request = (action.get("request") or action.get("text") or "").strip()
    if not request:
        raise ValueError("follow_up needs a request")
    try:
        task = await db.get(Task, UUID(str(action.get("task_id"))))
    except ValueError:
        task = None
    parent = await db.get(Task, task.parent_task_id) if task and task.parent_task_id else None
    if not task or not parent or parent.assigned_agent_id != from_agent.id or not task.assigned_agent_id:
        raise ValueError("follow_up needs the task_id of work you handed out")
    db.add(TaskComment(task_id=task.id, author=f"agent:{from_agent.slug}", body=request))
    if task.status != TaskStatus.IN_PROGRESS:
        task.status, task.completed_at = TaskStatus.IN_PROGRESS, None
    _start_after_commit(db, task.assigned_agent_id, task.id)
    return task
