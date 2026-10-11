"""
The coordinator: one agent that takes your requests and runs the team.

An agent whose skill file says `role: coordinator` gets requests from the
Telegram chat (and /do). For each one it either does the work itself or
splits it into handoffs to specialists, replying with status "waiting". It
gets its turn back once every handoff has settled (done, or waiting on you),
with the teammates' replies in its thread, and then answers you once. Your
replies go to the coordinator, which passes answers on with follow_up.

Teammates working for the coordinator don't message you themselves (unless
COORDINATOR_RELAY_TEAMMATES is set): the coordinator is the one voice.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentConfig, AgentStatus, Task, TaskComment, TaskStatus

ROLE = "coordinator"
MAX_HANDOFFS_PER_ROUND = 6
MAX_ROUNDS = 5
OPEN = (TaskStatus.TODO, TaskStatus.IN_PROGRESS)


def is_coordinator(agent: AgentConfig | None) -> bool:
    return bool(agent) and (agent.config or {}).get("role") == ROLE


async def get_coordinator(db: AsyncSession) -> AgentConfig | None:
    """The enabled coordinator agent, if there is one."""
    agents = (await db.execute(
        select(AgentConfig).where(AgentConfig.status != AgentStatus.DISABLED).order_by(AgentConfig.name)
    )).scalars().all()
    return next((a for a in agents if is_coordinator(a)), None)


async def handoffs_of(db: AsyncSession, task: Task) -> list[Task]:
    result = await db.execute(select(Task).where(Task.parent_task_id == task.id).order_by(Task.created_at))
    return list(result.scalars().all())


async def has_open_handoffs(db: AsyncSession, task: Task) -> bool:
    return any(t.status in OPEN for t in await handoffs_of(db, task))


async def coordinated_by(db: AsyncSession, task: Task) -> AgentConfig | None:
    """The coordinator this task was handed out by, if any."""
    if not task.parent_task_id:
        return None
    parent = await db.get(Task, task.parent_task_id)
    if not parent or not parent.assigned_agent_id:
        return None
    agent = await db.get(AgentConfig, parent.assigned_agent_id)
    return agent if is_coordinator(agent) else None


def rounds_used(thread: list[TaskComment], agent: AgentConfig) -> int:
    return sum(1 for c in thread if c.author == f"agent:{agent.slug}")


SYSTEM_PROMPT = f"""
## You coordinate the team
Requests from the user come to you. For each one:
- If you can do it well yourself (a quick answer, simple research or writing), do it: reply with
  the finished result and status "done".
- If it needs specialists, split it into clear pieces and hand each to the best teammate with a
  handoff action, giving them everything they need (they don't see the user's message). Pieces that
  don't depend on each other go out at once. A piece that needs another's result waits for a later
  round, once that result is in.
- After handing off, reply with a short plan for the user (who is doing what) and status "waiting".
  You get your turn back when your teammates have answered; their replies appear in the conversation.
- When the results are in, combine them into ONE finished answer: the deliverable itself (the
  findings, the draft), not a report on who did what. Status "done".
- If a teammate asks something you can answer from context, answer it with
  {{"type": "follow_up", "task_id": "<their task id>", "request": "<your answer>"}}. Otherwise ask the
  user (status "needs_input") and pass their answer on with follow_up, then reply with status "waiting".
- At most {MAX_HANDOFFS_PER_ROUND} handoffs per round and {MAX_ROUNDS} rounds per request.
"""


def team_status(handoffs: list[Task], rounds: int) -> str:
    """The coordinator's view of the work it handed out, for its prompt."""
    lines = []
    if handoffs:
        lines.append("\nWORK YOU HANDED OUT:")
        for t in handoffs:
            who = t.assigned_agent.slug if t.assigned_agent else "?"
            state = {
                TaskStatus.DONE: "done", TaskStatus.BLOCKED: "waiting for an answer",
            }.get(t.status, "working")
            lines.append(f"- [{state}] {who}: {t.text} (task_id {t.id})")
    if rounds >= MAX_ROUNDS - 1:
        lines.append("\nTHIS IS YOUR LAST ROUND: no more handoffs. Answer with what you have (status done or needs_input).")
    return "\n".join(lines)
