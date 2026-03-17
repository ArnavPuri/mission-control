from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Project, ProjectStatus

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
