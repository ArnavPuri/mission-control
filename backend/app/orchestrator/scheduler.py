"""
Agent Scheduler

Checks agent schedules and triggers runs automatically.
Supports:
  - interval: "4h", "30m", "1d"
  - cron: "0 9 * * *" (e.g., daily at 9am)
  - manual: only triggered via API/Telegram
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.db.models import AgentConfig, AgentStatus
from app.orchestrator.runner import AgentRunner

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

    def __init__(self, check_interval: int = 60, max_jitter: int = 30):
        self.check_interval = check_interval
        self.max_jitter = max_jitter  # seconds of random jitter to prevent thundering herd
        self.runner = AgentRunner()

    async def run(self):
        """Main scheduler loop."""
        logger.info("Scheduler started (interval + cron support)")
        await asyncio.sleep(self.check_interval)
        while True:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _check_schedules(self):
        """Check all agents for due schedules (both interval and cron)."""
        async with async_session() as db:
            result = await db.execute(
                select(AgentConfig).where(
                    AgentConfig.status == AgentStatus.IDLE,
                    AgentConfig.schedule_value.isnot(None),
                    or_(
                        AgentConfig.schedule_type == "interval",
                        AgentConfig.schedule_type == "cron",
                    ),
                )
            )
            agents = result.scalars().all()
            now = datetime.now(timezone.utc)

            due_agents = []
            for agent in agents:
                is_due = False

                if agent.schedule_type == "interval":
                    interval = parse_interval(agent.schedule_value)
                    if not interval:
                        continue
                    if agent.last_run_at:
                        if now >= agent.last_run_at + interval:
                            is_due = True
                    else:
                        is_due = True

                elif agent.schedule_type == "cron":
                    is_due = cron_is_due(agent.schedule_value, now, agent.last_run_at)

                if is_due:
                    due_agents.append(agent)

            # Launch all due agents concurrently with jitter
            async def _run_with_jitter(agent):
                jitter = random.uniform(0, self.max_jitter)
                if jitter > 1:
                    await asyncio.sleep(jitter)
                logger.info(
                    f"Scheduling agent: {agent.name} "
                    f"({agent.schedule_type}: {agent.schedule_value})"
                )
                try:
                    async with async_session() as agent_db:
                        await self.runner.start_run(agent, trigger="schedule", db=agent_db)
                        await agent_db.commit()
                except Exception as e:
                    logger.error(f"Failed to run agent {agent.name}: {e}")

            if due_agents:
                await asyncio.gather(*[_run_with_jitter(a) for a in due_agents])
