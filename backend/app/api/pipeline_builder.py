"""Pipeline Builder — visual-friendly API for creating and managing multi-agent workflows.

Extends the workflow DAG system with a builder API that makes it easy to
create pipelines from the dashboard, validate step dependencies, and preview execution plans.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentWorkflow, WorkflowStep, WorkflowStatus, StepStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class PipelineStepDef(BaseModel):
    agent_id: str
    name: str
    depends_on: list[str] = []  # list of step names this depends on
    config: dict = {}


class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    trigger_value: str | None = None
    steps: list[PipelineStepDef]


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    trigger_value: str | None = None


# --- Pipeline CRUD ---

@router.get("")
async def list_pipelines(db: AsyncSession = Depends(get_db)):
    """List all pipelines with step summaries."""
    result = await db.execute(
        select(AgentWorkflow).order_by(AgentWorkflow.created_at.desc())
    )
    workflows = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "status": w.status.value if w.status else "draft",
            "trigger_type": w.trigger_type,
            "trigger_value": w.trigger_value,
            "step_count": len(w.steps) if w.steps else 0,
            "steps": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "agent_id": str(s.agent_id),
                    "status": s.status.value if s.status else "pending",
                    "sort_order": s.sort_order,
                    "depends_on": s.depends_on or [],
                }
                for s in (w.steps or [])
            ],
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in workflows
    ]


@router.post("")
async def create_pipeline(data: PipelineCreate, db: AsyncSession = Depends(get_db)):
    """Create a new pipeline with steps and dependency validation.

    Steps are defined with names and dependencies (by step name).
    Dependencies are validated to prevent cycles and missing references.
    """
    # Validate agents exist
    for step in data.steps:
        agent = await db.get(AgentConfig, UUID(step.agent_id))
        if not agent:
            raise HTTPException(status_code=400, detail=f"Agent not found: {step.agent_id}")

    # Validate dependencies (no cycles, no missing refs)
    step_names = {s.name for s in data.steps}
    for step in data.steps:
        for dep in step.depends_on:
            if dep not in step_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"Step '{step.name}' depends on unknown step '{dep}'"
                )
            if dep == step.name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Step '{step.name}' cannot depend on itself"
                )

    # Check for cycles using topological sort
    if _has_cycle(data.steps):
        raise HTTPException(status_code=400, detail="Pipeline has circular dependencies")

    # Create workflow
    workflow = AgentWorkflow(
        name=data.name,
        description=data.description,
        status=WorkflowStatus.DRAFT,
        trigger_type=data.trigger_type,
        trigger_value=data.trigger_value,
    )
    db.add(workflow)
    await db.flush()

    # Create steps with topological ordering
    ordered_steps = _topological_sort(data.steps)
    step_id_map = {}

    for i, step_def in enumerate(ordered_steps):
        # Resolve dependency names to step IDs
        dep_ids = [step_id_map[dep] for dep in step_def.depends_on if dep in step_id_map]

        step = WorkflowStep(
            workflow_id=workflow.id,
            agent_id=UUID(step_def.agent_id),
            name=step_def.name,
            sort_order=i,
            depends_on=dep_ids,
            config=step_def.config,
        )
        db.add(step)
        await db.flush()
        step_id_map[step_def.name] = str(step.id)

    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "step_count": len(data.steps),
        "execution_order": [s.name for s in ordered_steps],
    }


@router.get("/{pipeline_id}/preview")
async def preview_execution(pipeline_id: UUID, db: AsyncSession = Depends(get_db)):
    """Preview the execution plan for a pipeline.

    Shows the order steps will execute, parallelization opportunities,
    and estimated costs.
    """
    workflow = await db.get(AgentWorkflow, pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    steps = workflow.steps or []
    if not steps:
        return {"pipeline": workflow.name, "steps": [], "parallel_groups": []}

    # Build dependency map
    step_map = {str(s.id): s for s in steps}
    dep_graph = {str(s.id): set(s.depends_on or []) for s in steps}

    # Group into parallel execution waves
    waves = []
    completed = set()
    remaining = set(dep_graph.keys())

    while remaining:
        # Find steps whose deps are all completed
        ready = {
            sid for sid in remaining
            if all(d in completed for d in dep_graph[sid])
        }
        if not ready:
            break  # shouldn't happen if acyclic

        wave = []
        for sid in ready:
            step = step_map[sid]
            agent = await db.get(AgentConfig, step.agent_id)
            wave.append({
                "step_id": sid,
                "name": step.name,
                "agent_name": agent.name if agent else "unknown",
                "agent_model": agent.model if agent else "unknown",
                "max_budget_usd": agent.max_budget_usd if agent else 0,
            })

        waves.append(wave)
        completed.update(ready)
        remaining -= ready

    total_budget = sum(
        s.get("max_budget_usd", 0) for wave in waves for s in wave
    )

    return {
        "pipeline": workflow.name,
        "total_steps": len(steps),
        "parallel_waves": len(waves),
        "estimated_max_cost_usd": round(total_budget, 4),
        "execution_plan": [
            {
                "wave": i + 1,
                "parallel": len(wave) > 1,
                "steps": wave,
            }
            for i, wave in enumerate(waves)
        ],
    }


@router.post("/{pipeline_id}/add-step")
async def add_step(
    pipeline_id: UUID,
    step: PipelineStepDef,
    db: AsyncSession = Depends(get_db),
):
    """Add a step to an existing pipeline."""
    workflow = await db.get(AgentWorkflow, pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    agent = await db.get(AgentConfig, UUID(step.agent_id))
    if not agent:
        raise HTTPException(status_code=400, detail="Agent not found")

    existing_steps = workflow.steps or []
    max_order = max((s.sort_order for s in existing_steps), default=-1)

    new_step = WorkflowStep(
        workflow_id=pipeline_id,
        agent_id=UUID(step.agent_id),
        name=step.name,
        sort_order=max_order + 1,
        depends_on=step.depends_on,
        config=step.config,
    )
    db.add(new_step)
    await db.flush()

    return {"step_id": str(new_step.id), "name": new_step.name, "sort_order": new_step.sort_order}


@router.delete("/{pipeline_id}/steps/{step_id}")
async def remove_step(pipeline_id: UUID, step_id: UUID, db: AsyncSession = Depends(get_db)):
    """Remove a step from a pipeline."""
    step = await db.get(WorkflowStep, step_id)
    if not step or step.workflow_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Step not found in this pipeline")

    await db.delete(step)
    return {"deleted": True}


# --- Helpers ---

def _has_cycle(steps: list[PipelineStepDef]) -> bool:
    """Check for cycles in step dependencies using DFS."""
    graph = {s.name: set(s.depends_on) for s in steps}
    visited = set()
    in_stack = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for dep in graph.get(node, set()):
            if dep in in_stack:
                return True
            if dep not in visited and dfs(dep):
                return True
        in_stack.discard(node)
        return False

    for node in graph:
        if node not in visited:
            if dfs(node):
                return True
    return False


def _topological_sort(steps: list[PipelineStepDef]) -> list[PipelineStepDef]:
    """Sort steps in topological order (dependencies first)."""
    graph = {s.name: set(s.depends_on) for s in steps}
    step_map = {s.name: s for s in steps}
    result = []
    visited = set()

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        for dep in graph.get(name, set()):
            visit(dep)
        result.append(step_map[name])

    for s in steps:
        visit(s.name)

    return result
