from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentStatus, Task, TaskComment, TaskStatus, TaskPriority
from app.integrations import github
from app.orchestrator import threads
from app.orchestrator.runner import is_running
from app.api.ws import broadcast

router = APIRouter()


class TaskCreate(BaseModel):
    text: str
    description: str | None = None
    url: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    project_id: UUID | None = None
    source: str = "manual"
    tags: list[str] = []
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    text: str | None = None
    description: str | None = None
    url: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    project_id: UUID | None = None
    tags: list[str] | None = None
    due_date: datetime | None = None


@router.get("")
async def list_tasks(
    status: TaskStatus | None = None,
    project_id: UUID | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).order_by(Task.sort_order.asc(), Task.priority.asc(), Task.created_at.desc())
    if status:
        query = query.where(Task.status == status)
    if project_id:
        query = query.where(Task.project_id == project_id)
    result = await db.execute(query)
    tasks = result.scalars().all()
    if tag:
        # tags is a JSON list; filter here so it works on PostgreSQL and SQLite
        tasks = [t for t in tasks if tag in (t.tags or [])]
    return [_serialize(t) for t in tasks]


def _serialize(t: Task) -> dict:
    return {
        "id": str(t.id),
        "text": t.text,
        "description": t.description,
        "url": t.url,
        "status": t.status.value,
        "priority": t.priority.value,
        "project_id": str(t.project_id) if t.project_id else None,
        "project_name": t.project.name if t.project else None,
        "project_has_repo": bool(t.project and t.project.github_repo),
        "github_issue": t.url if github.issue_ref(t) else None,
        "assigned_agent_id": str(t.assigned_agent_id) if t.assigned_agent_id else None,
        "assigned_agent_name": t.assigned_agent.name if t.assigned_agent else None,
        "source": t.source,
        "tags": t.tags or [],
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(),
    }


def _serialize_comment(c: TaskComment) -> dict:
    return {
        "id": str(c.id),
        "author": c.author,
        "body": c.body,
        "run_id": str(c.run_id) if c.run_id else None,
        "created_at": c.created_at.isoformat(),
    }


@router.get("/{task_id}")
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """A task with its full thread."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    thread = await threads.load_thread(db, task_id, limit=200)
    return {
        **_serialize(task),
        "agent_running": bool(task.assigned_agent_id) and is_running(task.assigned_agent_id),
        "comments": [_serialize_comment(c) for c in thread],
    }


class AssignRequest(BaseModel):
    agent_id: UUID | None = None  # None unassigns
    note: str | None = None


@router.post("/{task_id}/assign")
async def assign_task(task_id: UUID, data: AssignRequest, db: AsyncSession = Depends(get_db)):
    """Assign a task to an agent, which starts working on it (or unassign it)."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if data.agent_id is None:
        task.assigned_agent_id = None
        db.add(TaskComment(task_id=task.id, author=threads.SYSTEM, body="Unassigned"))
        await db.flush()
        return {"assigned": None}
    agent = await db.get(AgentConfig, data.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status == AgentStatus.DISABLED:
        raise HTTPException(status_code=409, detail="Agent is disabled")
    started = await threads.assign_task(db, task, agent, data.note)
    await broadcast("task.updated", {"id": str(task.id)})
    return {"assigned": agent.slug, "started": started}


@router.post("/{task_id}/github")
async def send_to_github(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """Turn a task into a GitHub issue in its project's repo for Claude Code."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if github.issue_ref(task):
        raise HTTPException(status_code=409, detail="Task already has a GitHub issue")
    if not task.project:
        raise HTTPException(status_code=400, detail="Set the task's project first")
    try:
        url = await github.open_dev_issue(db, task, task.project)
    except github.GitHubError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await broadcast("task.updated", {"id": str(task.id)})
    return {"issue_url": url}


class CommentCreate(BaseModel):
    body: str


@router.post("/{task_id}/comments")
async def add_comment(task_id: UUID, data: CommentCreate, db: AsyncSession = Depends(get_db)):
    """Reply in a task's thread. If an agent owns the task, it picks the reply up."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not data.body.strip():
        raise HTTPException(status_code=400, detail="Comment is empty")
    agent = await threads.add_user_reply(db, task, data.body.strip())
    await broadcast("task.updated", {"id": str(task.id)})
    return {"added": True, "agent": agent.slug if agent else None}


@router.post("")
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(**data.model_dump())
    db.add(task)
    await db.flush()
    return {"id": str(task.id), "text": task.text}


@router.patch("/{task_id}")
async def update_task(task_id: UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(task, key, val)
    if data.status == TaskStatus.DONE and not task.completed_at:
        task.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": str(task.id), "updated": True}


@router.delete("/{task_id}")
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"deleted": True}


class ReorderRequest(BaseModel):
    task_ids: list[str]  # ordered list of task IDs


@router.post("/reorder")
async def reorder_tasks(data: ReorderRequest, db: AsyncSession = Depends(get_db)):
    """Set sort_order for tasks based on the provided order."""
    for i, task_id in enumerate(data.task_ids):
        task = await db.get(Task, UUID(task_id))
        if task:
            task.sort_order = i
    await db.flush()
    return {"reordered": len(data.task_ids)}
