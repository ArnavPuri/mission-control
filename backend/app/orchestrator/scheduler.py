"""
Agent Scheduler

Checks agent schedules and triggers runs automatically.
Supports:
  - interval: "4h", "30m", "1d"
  - cron: "0 9 * * *" (e.g., daily at 9am in NOTIFICATION_TIMEZONE)
  - manual: only triggered via API/Telegram
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, or_

from app.config import settings
from app.db.session import async_session
from app.db.models import AgentConfig, AgentStatus
from app.orchestrator.runner import start_background_run
from app.orchestrator.threads import pending_assignments
from app.integrations import github

logger = logging.getLogger(__name__)

INTERVAL_PATTERN = re.compile(r"^(\d+)(m|h|d)$")


def parse_interval(value: str) -> timedelta | None:
    """Parse interval string like '4h', '30m', '1d' to timedelta."""
    match = INTERVAL_PATTERN.match(value.strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        return timedelta(minutes=amount)
    elif unit == "h":
        return timedelta(hours=amount)
    elif unit == "d":
        return timedelta(days=amount)
    return None


def cron_is_due(cron_expr: str, now: datetime, last_run: datetime | None) -> bool:
    """Check if a cron expression is due to run.

    Supports standard 5-field cron: minute hour day_of_month month day_of_week
    Simple matching — checks if current time matches the pattern.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, dom, month, dow = parts

    def matches(field: str, value: int, max_val: int) -> bool:
        if field == "*":
            return True
        # Handle */N step values
        if field.startswith("*/"):
            try:
                step = int(field[2:])
                return value % step == 0
            except ValueError:
                return False
        # Handle ranges like 1-5
        if "-" in field:
            try:
                low, high = field.split("-")
                return int(low) <= value <= int(high)
            except ValueError:
                return False
        # Handle comma-separated values
        if "," in field:
            try:
                return value in [int(v) for v in field.split(",")]
            except ValueError:
                return False
        # Plain number
        try:
            return value == int(field)
        except ValueError:
            return False

    if not matches(minute, now.minute, 59):
        return False
    if not matches(hour, now.hour, 23):
        return False
    if not matches(dom, now.day, 31):
        return False
    if not matches(month, now.month, 12):
        return False
    # day of week: 0=Monday in Python, but cron uses 0=Sunday
    # Convert Python weekday (Mon=0) to cron (Sun=0)
    cron_dow = (now.weekday() + 1) % 7
    if not matches(dow, cron_dow, 6):
        return False

    # Don't run if already ran this minute
    if last_run:
        if last_run.replace(second=0, microsecond=0) == now.replace(second=0, microsecond=0):
            return False

    return True


class Scheduler:
    """Periodically checks for agents that need to run."""

    def __init__(self, check_interval: int = 60, github_sync_every: int = 10):
        self.check_interval = check_interval
        self.github_sync_every = github_sync_every  # in scheduler ticks
        self._ticks = 0

    async def run(self):
        """Main scheduler loop."""
        logger.info("Scheduler started (interval + cron support)")
        await asyncio.sleep(self.check_interval)
        while True:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            self._ticks += 1
            if github.configured() and self._ticks % self.github_sync_every == 0:
                try:
                    async with async_session() as db:
                        await github.sync_dev_tasks(db)
                except Exception as e:
                    logger.error(f"GitHub sync error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _check_schedules(self):
        """Start every agent whose interval or cron schedule is due."""
        async with async_session() as db:
            result = await db.execute(
                select(AgentConfig).where(
                    # Agents whose last run failed stay on their schedule
                    AgentConfig.status.in_([AgentStatus.IDLE, AgentStatus.ERROR]),
                    AgentConfig.schedule_value.isnot(None),
                    or_(
                        AgentConfig.schedule_type == "interval",
                        AgentConfig.schedule_type == "cron",
                    ),
                )
            )
            agents = result.scalars().all()

            # Assigned tasks waiting on an agent that was busy go first
            pending = await pending_assignments(db)

        for agent_id, task_id in pending:
            if start_background_run(agent_id, trigger="task", task_id=task_id):
                logger.info(f"Picked up assigned task {task_id}")

        now = datetime.now(timezone.utc)
        for agent in agents:
            if is_due(agent, now) and start_background_run(agent.id, trigger="schedule"):
                logger.info(f"Scheduled run: {agent.name} ({agent.schedule_type}: {agent.schedule_value})")


def is_due(agent: AgentConfig, now: datetime) -> bool:
    if agent.schedule_type == "interval":
        interval = parse_interval(agent.schedule_value or "")
        if not interval:
            return False
        return agent.last_run_at is None or now >= _aware(agent.last_run_at) + interval
    if agent.schedule_type == "cron":
        # Cron expressions are in the user's timezone, like the morning briefing
        tz = ZoneInfo(settings.notification_timezone)
        last_run = _aware(agent.last_run_at).astimezone(tz) if agent.last_run_at else None
        return cron_is_due(agent.schedule_value, now.astimezone(tz), last_run)
    return False


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; everything is stored in UTC
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
