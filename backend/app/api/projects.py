from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import (
    Project, ProjectStatus, Task, TaskStatus,
    EventLog, MarketingSignal, MarketingContent,
)

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.PLANNING
    color: str = "#00ffc8"
    url: str | None = None
    metadata: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    color: str | None = None
    url: str | None = None
    metadata: dict | None = None


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    task_count_sq = (
        select(func.count(Task.id))
        .where(Task.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    open_task_count_sq = (
        select(func.count(Task.id))
        .where(Task.project_id == Project.id, Task.status != TaskStatus.DONE)
        .correlate(Project)
        .scalar_subquery()
    )
    content_count_sq = (
        select(func.count(MarketingContent.id))
        .where(MarketingContent.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            Project,
            task_count_sq.label("task_count"),
            open_task_count_sq.label("open_task_count"),
            content_count_sq.label("content_count"),
        ).order_by(Project.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "status": p.status.value,
            "color": p.color,
            "url": p.url,
            "metadata": p.metadata_ or {},
            "task_count": task_count,
            "open_task_count": open_task_count,
            "content_count": content_count,
            "agent_count": len(p.agents) if p.agents else 0,
            "created_at": p.created_at.isoformat(),
        }
        for p, task_count, open_task_count, content_count in rows
    ]


@router.post("")
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    fields = data.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_"] = fields.pop("metadata")
    project = Project(**fields)
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
        "metadata": project.metadata_ or {},
        "agent_count": len(project.agents) if project.agents else 0,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.patch("/{project_id}")
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    fields = data.model_dump(exclude_unset=True)
    if "metadata" in fields:
        fields["metadata_"] = fields.pop("metadata")
    for key, val in fields.items():
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
