"""Agent Workflows API — multi-step agent workflows with dependency resolution (DAGs)."""

import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import (
    AgentWorkflow, WorkflowStep, WorkflowStatus, StepStatus,
    AgentConfig, AgentStatus,
)
from app.api.ws import broadcast

logger = logging.getLogger(__name__)

router = APIRouter()


class StepCreate(BaseModel):
    agent_id: str
    name: str
    sort_order: int = 0
    depends_on: list[str] = []  # step IDs
    config: dict = {}


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    trigger_value: str | None = None
    steps: list[StepCreate] = []


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: WorkflowStatus | None = None
    trigger_type: str | None = None
    trigger_value: str | None = None


def _serialize_workflow(w: AgentWorkflow) -> dict:
    return {
        "id": str(w.id),
        "name": w.name,
        "description": w.description,
        "status": w.status.value,
        "trigger_type": w.trigger_type,
        "trigger_value": w.trigger_value,
        "steps": [
            {
                "id": str(s.id),
                "agent_id": str(s.agent_id),
                "agent_name": s.agent.name if s.agent else None,
                "name": s.name,
                "sort_order": s.sort_order,
                "depends_on": s.depends_on or [],
                "status": s.status.value,
                "config": s.config or {},
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "run_id": str(s.run_id) if s.run_id else None,
                "error": s.error,
            }
            for s in (w.steps or [])
        ],
        "created_at": w.created_at.isoformat(),
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


@router.get("")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentWorkflow).order_by(AgentWorkflow.created_at.desc()))
    return [_serialize_workflow(w) for w in result.scalars().all()]


@router.post("")
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    workflow = AgentWorkflow(
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_value=data.trigger_value,
    )
    db.add(workflow)
    await db.flush()

    for step_data in data.steps:
        step = WorkflowStep(
            workflow_id=workflow.id,
            agent_id=UUID(step_data.agent_id),
            name=step_data.name,
            sort_order=step_data.sort_order,
            depends_on=step_data.depends_on,
            config=step_data.config,
        )
        db.add(step)
    await db.flush()

    await db.refresh(workflow)
    return _serialize_workflow(workflow)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)):
    workflow = await db.get(AgentWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _serialize_workflow(workflow)


@router.patch("/{workflow_id}")
async def update_workflow(workflow_id: UUID, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    workflow = await db.get(AgentWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(workflow, key, val)
    await db.flush()
    return {"id": str(workflow.id), "updated": True}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)):
    workflow = await db.get(AgentWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    return {"deleted": True}


# --- Step management ---

@router.post("/{workflow_id}/steps")
async def add_step(workflow_id: UUID, data: StepCreate, db: AsyncSession = Depends(get_db)):
    workflow = await db.get(AgentWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    step = WorkflowStep(
        workflow_id=workflow_id,
        agent_id=UUID(data.agent_id),
        name=data.name,
        sort_order=data.sort_order,
        depends_on=data.depends_on,
        config=data.config,
    )
    db.add(step)
    await db.flush()
    return {"id": str(step.id), "name": step.name}


@router.delete("/{workflow_id}/steps/{step_id}")
async def remove_step(workflow_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    step = await db.get(WorkflowStep, step_id)
    if not step or step.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Step not found")
    await db.delete(step)
    return {"deleted": True}


# --- Execution ---

@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)):
    """Execute a workflow by resolving dependencies and running agents in order."""
    workflow = await db.get(AgentWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Workflow is already running")
    if not workflow.steps:
        raise HTTPException(status_code=400, detail="Workflow has no steps")

    # Validate DAG — check for missing dependencies
    step_ids = {str(s.id) for s in workflow.steps}
    for step in workflow.steps:
        for dep in (step.depends_on or []):
            if dep not in step_ids:
                raise HTTPException(status_code=400, detail=f"Step '{step.name}' depends on unknown step '{dep}'")

    # Reset all steps to pending
    for step in workflow.steps:
        step.status = StepStatus.PENDING
        step.started_at = None
        step.completed_at = None
        step.run_id = None
        step.error = None

    workflow.status = WorkflowStatus.RUNNING
    await db.flush()

    await broadcast("workflow.started", {"id": str(workflow.id), "name": workflow.name})

    # Execute in background
    asyncio.create_task(_execute_workflow(workflow_id))

    return {"id": str(workflow.id), "status": "running", "steps": len(workflow.steps)}


async def _execute_workflow(workflow_id: UUID):
    """Background task: execute workflow steps respecting dependencies."""
    from app.db.session import async_session
    from app.orchestrator.runner import AgentRunner

    runner = AgentRunner()

    async with async_session() as db:
        workflow = await db.get(AgentWorkflow, workflow_id)
        if not workflow:
            return

        steps = list(workflow.steps)
        completed_ids: set[str] = set()
        failed = False

        while not failed:
            # Find ready steps: pending + all dependencies completed
            ready = [
                s for s in steps
                if s.status == StepStatus.PENDING
                and all(dep in completed_ids for dep in (s.depends_on or []))
            ]

            if not ready:
                # Either done or stuck
                break

            # Run ready steps (could be parallel, but sequential is safer)
            for step in ready:
                agent = await db.get(AgentConfig, step.agent_id)
                if not agent or agent.status == AgentStatus.RUNNING:
                    step.status = StepStatus.SKIPPED
                    step.error = "Agent unavailable"
                    await db.flush()
                    continue

                step.status = StepStatus.RUNNING
                step.started_at = datetime.now(timezone.utc)
                await db.flush()

                try:
                    run = await runner.start_run(agent, trigger=f"workflow:{workflow.name}", db=db)
                    step.run_id = run.id
                    if run.status.value == "completed":
                        step.status = StepStatus.COMPLETED
                        step.completed_at = datetime.now(timezone.utc)
                        completed_ids.add(str(step.id))
                    else:
                        step.status = StepStatus.FAILED
                        step.error = run.error or "Run did not complete"
                        failed = True
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)[:500]
                    failed = True

                await db.flush()

                if failed:
                    break

        # Mark remaining pending steps as skipped if workflow failed
        if failed:
            for s in steps:
                if s.status == StepStatus.PENDING:
                    s.status = StepStatus.SKIPPED

        workflow.status = WorkflowStatus.COMPLETED if not failed else WorkflowStatus.FAILED
        await db.flush()
        await db.commit()

        await broadcast("workflow.completed", {
            "id": str(workflow.id),
            "name": workflow.name,
            "status": workflow.status.value,
        })
