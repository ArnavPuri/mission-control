"""User Pattern Learning API.

Analyzes user activity patterns (task creation times, journal entries, habit completions)
to adapt agent schedules and provide personalized timing recommendations.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import (
    Task, Idea, EventLog,
    AgentConfig, AgentRun, AgentRunStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/activity-patterns")
async def get_activity_patterns(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Analyze user activity patterns over a time window.

    Returns hourly and daily distributions of activity, peak hours,
    and recommended scheduling windows.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Collect timestamps from multiple sources
    timestamps: list[datetime] = []

    # Tasks
    result = await db.execute(
        select(Task.created_at).where(Task.created_at >= since)
    )
    timestamps.extend(r[0] for r in result.all() if r[0])

    # Ideas
    result = await db.execute(
        select(Idea.created_at).where(Idea.created_at >= since)
    )
    timestamps.extend(r[0] for r in result.all() if r[0])

    # Event log
    result = await db.execute(
        select(EventLog.created_at).where(
            EventLog.created_at >= since,
            EventLog.source == "manual",
        )
    )
    timestamps.extend(r[0] for r in result.all() if r[0])

    if not timestamps:
        return {
            "period_days": days,
            "total_events": 0,
            "hourly_distribution": {},
            "daily_distribution": {},
            "peak_hours": [],
            "quiet_hours": [],
            "recommendations": [],
        }

    # Hourly distribution
    hourly = Counter(ts.hour for ts in timestamps)
    hourly_dist = {h: hourly.get(h, 0) for h in range(24)}

    # Daily distribution (0=Monday)
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    daily = Counter(ts.weekday() for ts in timestamps)
    daily_dist = {day_names[d]: daily.get(d, 0) for d in range(7)}

    # Peak hours (top 4)
    sorted_hours = sorted(hourly_dist.items(), key=lambda x: x[1], reverse=True)
    peak_hours = [h for h, _ in sorted_hours[:4] if hourly_dist[h] > 0]

    # Quiet hours (bottom hours with 0 or minimal activity)
    quiet_hours = [h for h, c in sorted_hours if c == 0] or [h for h, _ in sorted_hours[-4:]]

    # Generate recommendations
    recommendations = _generate_recommendations(hourly_dist, daily_dist, peak_hours, quiet_hours)

    return {
        "period_days": days,
        "total_events": len(timestamps),
        "hourly_distribution": hourly_dist,
        "daily_distribution": daily_dist,
        "peak_hours": peak_hours,
        "quiet_hours": quiet_hours[:6],
        "recommendations": recommendations,
    }


@router.get("/schedule-suggestions")
async def get_schedule_suggestions(db: AsyncSession = Depends(get_db)):
    """Suggest optimal schedules for each agent based on user activity patterns.

    Analyzes when the user is most active and maps agent types to appropriate windows:
    - Planning agents -> early in user's active window
    - Review agents -> end of user's active window
    - Background agents -> quiet hours
    """
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # Get activity pattern
    timestamps: list[datetime] = []
    result = await db.execute(select(Task.created_at).where(Task.created_at >= since))
    timestamps.extend(r[0] for r in result.all() if r[0])
    result = await db.execute(select(EventLog.created_at).where(EventLog.created_at >= since))
    timestamps.extend(r[0] for r in result.all() if r[0])

    hourly = Counter(ts.hour for ts in timestamps)

    # Find active window
    if hourly:
        sorted_hours = sorted(hourly.keys(), key=lambda h: hourly[h], reverse=True)
        active_start = min(sorted_hours[:6]) if len(sorted_hours) >= 6 else 8
        active_end = max(sorted_hours[:6]) if len(sorted_hours) >= 6 else 20
    else:
        active_start, active_end = 8, 20

    # Get agents with schedules
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.schedule_value.isnot(None))
    )
    agents = result.scalars().all()

    # Get agent success rates
    agent_stats = {}
    for agent in agents:
        runs_result = await db.execute(
            select(AgentRun).where(
                AgentRun.agent_id == agent.id,
                AgentRun.started_at >= since,
            )
        )
        runs = runs_result.scalars().all()
        total = len(runs)
        successes = sum(1 for r in runs if r.status == AgentRunStatus.COMPLETED)
        agent_stats[str(agent.id)] = {
            "total_runs": total,
            "success_rate": successes / total if total > 0 else 0,
        }

    suggestions = []
    for agent in agents:
        agent_type = (agent.agent_type or "general").lower()
        config = agent.config or {}
        persona = config.get("persona", "").lower()

        # Determine optimal time window
        if any(k in agent_type or k in persona for k in ["morning", "standup", "planning", "brief"]):
            suggested_hour = active_start
            reason = "Scheduled at start of your active window for morning planning"
        elif any(k in agent_type or k in persona for k in ["evening", "review", "reflection", "summary"]):
            suggested_hour = active_end
            reason = "Scheduled at end of your active window for reflection"
        elif any(k in agent_type or k in persona for k in ["scout", "monitor", "feed", "background"]):
            suggested_hour = (active_start - 2) % 24
            reason = "Scheduled before your active window so results are ready"
        else:
            # Default: middle of active window
            suggested_hour = (active_start + active_end) // 2
            reason = "Scheduled during your peak activity hours"

        suggested_cron = f"0 {suggested_hour} * * *"
        stats = agent_stats.get(str(agent.id), {})

        suggestions.append({
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "current_schedule": f"{agent.schedule_type}: {agent.schedule_value}",
            "suggested_schedule": f"cron: {suggested_cron}",
            "suggested_hour": suggested_hour,
            "reason": reason,
            "success_rate": round(stats.get("success_rate", 0), 2),
            "total_runs": stats.get("total_runs", 0),
        })

    return {
        "active_window": {"start": active_start, "end": active_end},
        "suggestions": suggestions,
    }


def _generate_recommendations(
    hourly: dict[int, int],
    daily: dict[str, int],
    peak_hours: list[int],
    quiet_hours: list[int],
) -> list[dict]:
    """Generate scheduling recommendations from activity data."""
    recs = []

    if peak_hours:
        peak_str = ", ".join(f"{h}:00" for h in sorted(peak_hours))
        recs.append({
            "type": "peak_activity",
            "message": f"Your peak activity hours are {peak_str}. "
                       "Schedule planning/standup agents just before these windows.",
            "hours": sorted(peak_hours),
        })

    if quiet_hours:
        quiet_str = ", ".join(f"{h}:00" for h in sorted(quiet_hours[:4]))
        recs.append({
            "type": "quiet_window",
            "message": f"Your quiet hours are around {quiet_str}. "
                       "Schedule background/scout agents during these times.",
            "hours": sorted(quiet_hours[:4]),
        })

    # Most active day
    if daily:
        best_day = max(daily.items(), key=lambda x: x[1])
        least_day = min(daily.items(), key=lambda x: x[1])
        if best_day[1] > 0:
            recs.append({
                "type": "weekly_pattern",
                "message": f"You're most active on {best_day[0].title()}s "
                           f"and least active on {least_day[0].title()}s. "
                           "Consider scheduling weekly review agents on your most active days.",
                "best_day": best_day[0],
                "least_day": least_day[0],
            })

    return recs
