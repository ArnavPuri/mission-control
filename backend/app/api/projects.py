from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import (
    Project, ProjectStatus, Task, TaskStatus, Goal, GoalStatus,
    AgentRun, AgentRunStatus, EventLog,
)

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.PLANNING
    color: str = "#00ffc8"
    url: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    color: str | None = None
    url: str | None = None


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "status": p.status.value,
            "color": p.color,
            "url": p.url,
            "task_count": len(p.tasks) if p.tasks else 0,
            "agent_count": len(p.agents) if p.agents else 0,
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]


@router.post("")
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()
    return {"id": str(project.id), "name": project.name}


@router.get("/{project_id}")
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value,
        "color": project.color,
        "url": project.url,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.patch("/{project_id}")
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(project, key, val)
    await db.flush()
    return {"id": str(project.id), "updated": True}


@router.delete("/{project_id}")
async def delete_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    return {"deleted": True}


@router.get("/{project_id}/health")
async def project_health(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Calculate project health score and return detailed metrics."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Task metrics
    all_tasks = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = all_tasks.scalars().all()
    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    overdue_tasks = sum(
        1 for t in tasks
        if t.due_date and t.due_date < now and t.status != TaskStatus.DONE
    )
    blocked_tasks = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)

    # Completion rate
    completion_rate = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Recent velocity — tasks completed in last 7 days
    recent_completions = sum(
        1 for t in tasks
        if t.status == TaskStatus.DONE
        and t.completed_at
        and t.completed_at >= seven_days_ago
    )

    # Goal progress
    goals_result = await db.execute(
        select(Goal).where(
            Goal.project_id == project_id,
            Goal.status == GoalStatus.ACTIVE,
        )
    )
    goals = goals_result.scalars().all()
    avg_goal_progress = (
        sum(g.progress for g in goals) / len(goals)
        if goals else 0
    )

    # Recent activity — events in last 30 days
    activity_count = await db.scalar(
        select(func.count(EventLog.id)).where(
            EventLog.entity_id == project_id,
            EventLog.created_at >= thirty_days_ago,
        )
    ) or 0

    # Also count task-level activity for this project
    task_ids = [t.id for t in tasks]
    if task_ids:
        task_activity = await db.scalar(
            select(func.count(EventLog.id)).where(
                EventLog.entity_id.in_(task_ids),
                EventLog.created_at >= thirty_days_ago,
            )
        ) or 0
        activity_count += task_activity

    # Calculate health score (0-100)
    score = 100
    # Penalize for overdue tasks (-5 each, max -30)
    score -= min(overdue_tasks * 5, 30)
    # Penalize for blocked tasks (-3 each, max -15)
    score -= min(blocked_tasks * 3, 15)
    # Penalize for low completion rate
    if total_tasks > 5 and completion_rate < 20:
        score -= 20
    elif total_tasks > 5 and completion_rate < 50:
        score -= 10
    # Reward recent velocity
    if recent_completions >= 5:
        score += 5
    elif recent_completions == 0 and total_tasks > 3:
        score -= 10
    # Penalize for inactivity
    if activity_count == 0 and total_tasks > 0:
        score -= 15
    # Factor in goal progress
    if goals:
        score += int(avg_goal_progress * 10)  # up to +10

    score = max(0, min(100, score))

    # Determine status color
    if score >= 70:
        status = "healthy"
    elif score >= 40:
        status = "needs_attention"
    else:
        status = "at_risk"

    return {
        "project_id": str(project_id),
        "project_name": project.name,
        "score": score,
        "status": status,
        "metrics": {
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks": blocked_tasks,
            "completion_rate": round(completion_rate, 1),
            "weekly_velocity": recent_completions,
            "active_goals": len(goals),
            "avg_goal_progress": round(avg_goal_progress * 100, 1),
            "monthly_activity": activity_count,
        },
    }
