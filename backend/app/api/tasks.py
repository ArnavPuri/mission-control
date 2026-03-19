from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Task, TaskStatus, TaskPriority

router = APIRouter()


class TaskCreate(BaseModel):
    text: str
    priority: TaskPriority = TaskPriority.MEDIUM
    project_id: UUID | None = None
    source: str = "manual"
    tags: list[str] = []
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    text: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    project_id: UUID | None = None
    tags: list[str] | None = None
    due_date: datetime | None = None


@router.get("")
async def list_tasks(
    status: TaskStatus | None = None,
    project_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).order_by(Task.sort_order.asc(), Task.priority.asc(), Task.created_at.desc())
    if status:
        query = query.where(Task.status == status)
    if project_id:
        query = query.where(Task.project_id == project_id)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "text": t.text,
            "status": t.status.value,
            "priority": t.priority.value,
            "project_id": str(t.project_id) if t.project_id else None,
            "source": t.source,
            "tags": t.tags or [],
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("")
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(**data.model_dump())
    db.add(task)
    await db.flush()

    # Evaluate conditional triggers
    try:
        from app.api.triggers import evaluate_triggers
        await evaluate_triggers("task", "created", {
            "text": task.text, "priority": task.priority.value, "status": task.status.value,
            "tags": task.tags or [], "source": task.source,
        }, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Trigger evaluation failed: {e}")

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
