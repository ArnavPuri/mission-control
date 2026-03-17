from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentStatus, AgentRunStatus
from app.orchestrator.runner import AgentRunner

router = APIRouter()


@router.get("")
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.name))
    agents = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "slug": a.slug,
            "description": a.description,
            "agent_type": a.agent_type,
            "status": a.status.value,
            "model": a.model,
            "schedule_type": a.schedule_type,
            "schedule_value": a.schedule_value,
            "project_id": str(a.project_id) if a.project_id else None,
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "recent_runs": [
                {
                    "id": str(r.id),
                    "status": r.status.value,
                    "cost_usd": r.cost_usd,
                    "started_at": r.started_at.isoformat(),
                }
                for r in (a.runs or [])[:5]
            ],
        }
        for a in agents
    ]


@router.post("/{agent_id}/run")
async def trigger_agent(agent_id: UUID, dry_run: bool = False, db: AsyncSession = Depends(get_db)):
    """Manually trigger an agent run. Set dry_run=true to preview without executing actions."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status == AgentStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Agent is already running")

    runner = AgentRunner()

    if dry_run:
        # Build context and show the rendered prompt + config without executing
        context = await runner.build_context(agent, db)
        prompt = runner.render_prompt(agent.prompt_template, context)
        return {
            "dry_run": True,
            "agent": agent.name,
            "model": agent.model,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:2000] + ("..." if len(prompt) > 2000 else ""),
            "context_keys": list(context.keys()),
            "context_sizes": {k: len(v) if isinstance(v, list) else 1 for k, v in context.items()},
            "tools": agent.tools or [],
            "data_reads": agent.data_reads or [],
            "data_writes": agent.data_writes or [],
            "requires_approval": agent.config.get("requires_approval", False) if agent.config else False,
            "max_budget_usd": agent.max_budget_usd,
        }

    run = await runner.start_run(agent, trigger="manual", db=db)
    return {"run_id": str(run.id), "status": "started"}


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Stop a running agent."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.IDLE
    await db.flush()
    return {"status": "stopped"}


@router.get("/{agent_id}/runs")
async def list_agent_runs(agent_id: UUID, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.agent_id == agent_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status.value,
            "trigger": r.trigger,
            "tokens_used": r.tokens_used,
            "cost_usd": r.cost_usd,
            "error": r.error,
            "output_data": r.output_data,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]
