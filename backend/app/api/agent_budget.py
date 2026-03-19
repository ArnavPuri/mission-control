"""Agent Budget Management Dashboard.

Track spending per agent, set budget limits, and get alerts
when agents approach or exceed their budget thresholds.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class BudgetUpdate(BaseModel):
    daily_limit_usd: float | None = None
    weekly_limit_usd: float | None = None
    monthly_limit_usd: float | None = None
    alert_threshold: float = 0.8  # alert at 80% of budget


# --- Budget Dashboard ---

@router.get("/overview")
async def budget_overview(db: AsyncSession = Depends(get_db)):
    """Get a comprehensive budget overview for all agents.

    Shows current spending, budget limits, and alerts for each agent.
    """
    result = await db.execute(select(AgentConfig))
    agents = result.scalars().all()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    overview = []
    total_daily = 0.0
    total_weekly = 0.0
    total_monthly = 0.0
    alerts = []

    for agent in agents:
        # Get spending for each period
        daily_cost = await _get_spending(db, agent.id, today_start)
        weekly_cost = await _get_spending(db, agent.id, week_start)
        monthly_cost = await _get_spending(db, agent.id, month_start)

        total_daily += daily_cost
        total_weekly += weekly_cost
        total_monthly += monthly_cost

        # Check budget limits
        config = agent.config or {}
        budget = config.get("_budget", {})
        daily_limit = budget.get("daily_limit_usd")
        weekly_limit = budget.get("weekly_limit_usd")
        monthly_limit = budget.get("monthly_limit_usd")
        threshold = budget.get("alert_threshold", 0.8)

        agent_alerts = []
        if daily_limit and daily_cost >= daily_limit * threshold:
            level = "exceeded" if daily_cost >= daily_limit else "warning"
            agent_alerts.append({
                "type": "daily",
                "level": level,
                "spent": round(daily_cost, 4),
                "limit": daily_limit,
                "percent": round(daily_cost / daily_limit * 100, 1),
            })

        if weekly_limit and weekly_cost >= weekly_limit * threshold:
            level = "exceeded" if weekly_cost >= weekly_limit else "warning"
            agent_alerts.append({
                "type": "weekly",
                "level": level,
                "spent": round(weekly_cost, 4),
                "limit": weekly_limit,
                "percent": round(weekly_cost / weekly_limit * 100, 1),
            })

        if monthly_limit and monthly_cost >= monthly_limit * threshold:
            level = "exceeded" if monthly_cost >= monthly_limit else "warning"
            agent_alerts.append({
                "type": "monthly",
                "level": level,
                "spent": round(monthly_cost, 4),
                "limit": monthly_limit,
                "percent": round(monthly_cost / monthly_limit * 100, 1),
            })

        if agent_alerts:
            for a in agent_alerts:
                alerts.append({"agent_name": agent.name, "agent_id": str(agent.id), **a})

        overview.append({
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "max_budget_per_run": agent.max_budget_usd,
            "spending": {
                "daily": round(daily_cost, 4),
                "weekly": round(weekly_cost, 4),
                "monthly": round(monthly_cost, 4),
            },
            "limits": {
                "daily": daily_limit,
                "weekly": weekly_limit,
                "monthly": monthly_limit,
            },
            "alerts": agent_alerts,
        })

    # Sort by monthly spending descending
    overview.sort(key=lambda x: x["spending"]["monthly"], reverse=True)

    return {
        "totals": {
            "daily": round(total_daily, 4),
            "weekly": round(total_weekly, 4),
            "monthly": round(total_monthly, 4),
        },
        "agent_count": len(agents),
        "alerts": alerts,
        "agents": overview,
    }


@router.get("/{agent_id}/spending")
async def agent_spending_detail(
    agent_id: UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed spending history for a specific agent."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(AgentRun).where(
            AgentRun.agent_id == agent_id,
            AgentRun.started_at >= since,
        ).order_by(AgentRun.started_at.desc())
    )
    runs = result.scalars().all()

    # Daily breakdown
    daily_spending: dict[str, float] = {}
    for run in runs:
        day = run.started_at.strftime("%Y-%m-%d") if run.started_at else "unknown"
        daily_spending[day] = daily_spending.get(day, 0) + (run.cost_usd or 0)

    total_cost = sum(r.cost_usd or 0 for r in runs)
    total_tokens = sum(r.tokens_used or 0 for r in runs)
    completed = sum(1 for r in runs if r.status == AgentRunStatus.COMPLETED)

    return {
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "period_days": days,
        "total_runs": len(runs),
        "completed_runs": completed,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "avg_cost_per_run": round(total_cost / len(runs), 4) if runs else 0,
        "daily_spending": dict(sorted(daily_spending.items())),
    }


@router.patch("/{agent_id}/limits")
async def set_budget_limits(
    agent_id: UUID,
    data: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Set budget limits and alert thresholds for an agent."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    config = dict(agent.config or {})
    budget = config.get("_budget", {})

    if data.daily_limit_usd is not None:
        budget["daily_limit_usd"] = data.daily_limit_usd
    if data.weekly_limit_usd is not None:
        budget["weekly_limit_usd"] = data.weekly_limit_usd
    if data.monthly_limit_usd is not None:
        budget["monthly_limit_usd"] = data.monthly_limit_usd
    budget["alert_threshold"] = data.alert_threshold

    config["_budget"] = budget
    agent.config = config
    await db.flush()

    return {"updated": True, "agent_name": agent.name, "limits": budget}


async def _get_spending(db: AsyncSession, agent_id: UUID, since: datetime) -> float:
    """Get total spending for an agent since a given time."""
    result = await db.execute(
        select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)).where(
            AgentRun.agent_id == agent_id,
            AgentRun.started_at >= since,
        )
    )
    return float(result.scalar() or 0.0)


async def check_budget_before_run(agent: AgentConfig, db: AsyncSession) -> tuple[bool, str]:
    """Check if an agent is within budget before running.

    Returns (allowed, message). Called by the runner before execution.
    """
    config = agent.config or {}
    budget = config.get("_budget", {})

    if not budget:
        return True, ""

    now = datetime.now(timezone.utc)

    # Check daily limit
    daily_limit = budget.get("daily_limit_usd")
    if daily_limit:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_spent = await _get_spending(db, agent.id, today_start)
        if daily_spent >= daily_limit:
            return False, f"Daily budget exceeded (${daily_spent:.4f} / ${daily_limit})"

    # Check weekly limit
    weekly_limit = budget.get("weekly_limit_usd")
    if weekly_limit:
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start -= timedelta(days=now.weekday())
        weekly_spent = await _get_spending(db, agent.id, week_start)
        if weekly_spent >= weekly_limit:
            return False, f"Weekly budget exceeded (${weekly_spent:.4f} / ${weekly_limit})"

    # Check monthly limit
    monthly_limit = budget.get("monthly_limit_usd")
    if monthly_limit:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_spent = await _get_spending(db, agent.id, month_start)
        if monthly_spent >= monthly_limit:
            return False, f"Monthly budget exceeded (${monthly_spent:.4f} / ${monthly_limit})"

    return True, ""
