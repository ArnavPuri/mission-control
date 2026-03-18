import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentStatus, AgentRunStatus, EventLog
from app.orchestrator.runner import AgentRunner
from app.api.ws import broadcast

router = APIRouter()


def _slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _serialize_full(a: AgentConfig) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "slug": a.slug,
        "description": a.description,
        "agent_type": a.agent_type,
        "status": a.status.value,
        "model": a.model,
        "max_budget_usd": a.max_budget_usd,
        "prompt_template": a.prompt_template,
        "tools": a.tools or [],
        "schedule_type": a.schedule_type,
        "schedule_value": a.schedule_value,
        "data_reads": a.data_reads or [],
        "data_writes": a.data_writes or [],
        "project_id": str(a.project_id) if a.project_id else None,
        "config": a.config or {},
        "skill_file": a.skill_file,
        "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


class AgentCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str = ""
    agent_type: str = "marketing"
    model: str = "claude-haiku-4-5"
    max_budget_usd: float = 0.10
    prompt_template: str
    tools: list[str] = []
    schedule_type: str | None = None
    schedule_value: str | None = None
    data_reads: list[str] = []
    data_writes: list[str] = []
    project_id: str | None = None
    config: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    agent_type: str | None = None
    model: str | None = None
    max_budget_usd: float | None = None
    prompt_template: str | None = None
    tools: list[str] | None = None
    schedule_type: str | None = None
    schedule_value: str | None = None
    data_reads: list[str] | None = None
    data_writes: list[str] | None = None
    project_id: str | None = None
    config: dict | None = None
    status: str | None = None  # only idle or disabled


# ─── List ─────────────────────────────────────────────────

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


# ─── Create ───────────────────────────────────────────────

@router.post("")
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    slug = data.slug or _slugify(data.name)

    # Check name uniqueness
    existing_name = await db.execute(select(AgentConfig).where(AgentConfig.name == data.name))
    if existing_name.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent name already exists")

    # Check slug uniqueness
    existing_slug = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
    if existing_slug.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent slug already exists")

    agent = AgentConfig(
        name=data.name,
        slug=slug,
        description=data.description,
        agent_type=data.agent_type,
        model=data.model,
        max_budget_usd=data.max_budget_usd,
        prompt_template=data.prompt_template,
        tools=data.tools,
        schedule_type=data.schedule_type,
        schedule_value=data.schedule_value,
        data_reads=data.data_reads,
        data_writes=data.data_writes,
        project_id=UUID(data.project_id) if data.project_id else None,
        config=data.config,
        skill_file=None,  # UI-created agents have no skill file
    )
    db.add(agent)
    await db.flush()
    db.add(EventLog(
        event_type="agent.created", entity_type="agent",
        entity_id=agent.id, source="dashboard",
        data={"name": agent.name, "agent_type": agent.agent_type},
    ))
    await broadcast("agent.created", {"id": str(agent.id), "name": agent.name})
    return _serialize_full(agent)


# ─── Detail ───────────────────────────────────────────────

@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _serialize_full(agent)


# ─── Update ───────────────────────────────────────────────

@router.patch("/{agent_id}")
async def update_agent(agent_id: UUID, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates = data.model_dump(exclude_unset=True)

    # Validate name uniqueness if changing
    if "name" in updates and updates["name"] != agent.name:
        existing = await db.execute(select(AgentConfig).where(AgentConfig.name == updates["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Agent name already exists")

    # Validate slug uniqueness if changing
    if "slug" in updates and updates["slug"] != agent.slug:
        existing = await db.execute(select(AgentConfig).where(AgentConfig.slug == updates["slug"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Agent slug already exists")

    # Restrict status changes to idle/disabled
    if "status" in updates:
        if updates["status"] not in ("idle", "disabled"):
            raise HTTPException(status_code=400, detail="Status can only be set to idle or disabled")
        updates["status"] = AgentStatus(updates["status"])

    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None

    for key, val in updates.items():
        setattr(agent, key, val)
    await db.flush()
    return _serialize_full(agent)


# ─── Delete (soft) ────────────────────────────────────────

@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.DISABLED
    await db.flush()
    return {"disabled": True}


# ─── Run ──────────────────────────────────────────────────

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


# ─── Stop ─────────────────────────────────────────────────

@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Stop a running agent."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.IDLE
    await db.flush()
    return {"status": "stopped"}


# ─── List Runs ────────────────────────────────────────────

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
