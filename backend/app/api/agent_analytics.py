"""Agent Performance Analytics — track success rates, costs, and efficiency."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentRunStatus

router = APIRouter()


@router.get("/overview")
async def analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get performance overview for all agents."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all agents
    agents_result = await db.execute(select(AgentConfig))
    agents = agents_result.scalars().all()

    overview = []
    for agent in agents:
        runs_result = await db.execute(
            select(AgentRun).where(
                AgentRun.agent_id == agent.id,
                AgentRun.started_at >= cutoff,
            ).order_by(AgentRun.started_at.desc())
        )
        runs = runs_result.scalars().all()

        total = len(runs)
        completed = sum(1 for r in runs if r.status == AgentRunStatus.COMPLETED)
        failed = sum(1 for r in runs if r.status == AgentRunStatus.FAILED)
        total_cost = sum(r.cost_usd or 0 for r in runs)
        total_tokens = sum(r.tokens_used or 0 for r in runs)

        # Average run duration (completed runs only)
        durations = []
        for r in runs:
            if r.completed_at and r.started_at:
                dur = (r.completed_at - r.started_at).total_seconds()
                durations.append(dur)

        avg_duration = sum(durations) / len(durations) if durations else 0

        # Daily cost breakdown
        daily_costs: dict[str, float] = {}
        for r in runs:
            day = r.started_at.date().isoformat()
            daily_costs[day] = daily_costs.get(day, 0) + (r.cost_usd or 0)

        overview.append({
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "agent_slug": agent.slug,
            "model": agent.model,
            "total_runs": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "avg_cost_per_run": round(total_cost / total, 4) if total > 0 else 0,
            "avg_duration_seconds": round(avg_duration, 1),
            "avg_tokens_per_run": total_tokens // total if total > 0 else 0,
            "daily_costs": daily_costs,
            "last_run_at": agent.last_run_at.isoformat() if agent.last_run_at else None,
        })

    # Sort by total runs descending
    overview.sort(key=lambda x: x["total_runs"], reverse=True)

    # Totals
    total_cost = sum(a["total_cost_usd"] for a in overview)
    total_runs = sum(a["total_runs"] for a in overview)
    total_completed = sum(a["completed"] for a in overview)

    return {
        "days": days,
        "agents": overview,
        "totals": {
            "total_agents": len(agents),
            "total_runs": total_runs,
            "total_completed": total_completed,
            "total_failed": total_runs - total_completed,
            "overall_success_rate": total_completed / total_runs if total_runs > 0 else 0,
            "total_cost_usd": round(total_cost, 4),
        },
    }


@router.get("/{agent_id}")
async def agent_analytics(
    agent_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed analytics for a specific agent."""
    from uuid import UUID as UUIDType
    agent = await db.get(AgentConfig, UUIDType(agent_id))
    if not agent:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs_result = await db.execute(
        select(AgentRun).where(
            AgentRun.agent_id == agent.id,
            AgentRun.started_at >= cutoff,
        ).order_by(AgentRun.started_at.desc())
    )
    runs = runs_result.scalars().all()

    run_details = []
    for r in runs:
        duration = None
        if r.completed_at and r.started_at:
            duration = round((r.completed_at - r.started_at).total_seconds(), 1)

        action_count = 0
        if r.output_data and isinstance(r.output_data, dict):
            action_count = len(r.output_data.get("actions", []))

        run_details.append({
            "id": str(r.id),
            "status": r.status.value,
            "trigger": r.trigger,
            "cost_usd": r.cost_usd or 0,
            "tokens_used": r.tokens_used or 0,
            "duration_seconds": duration,
            "action_count": action_count,
            "error": r.error,
            "started_at": r.started_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })

    total = len(runs)
    completed = sum(1 for r in runs if r.status == AgentRunStatus.COMPLETED)

    return {
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "days": days,
        "total_runs": total,
        "success_rate": completed / total if total > 0 else 0,
        "total_cost_usd": round(sum(r.cost_usd or 0 for r in runs), 4),
        "runs": run_details,
    }
