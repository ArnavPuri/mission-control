"""
Agent Scheduler

Checks agent schedules and triggers runs automatically.
Supports:
  - interval: "4h", "30m", "1d"
  - cron: "0 9 * * *" (future)
  - manual: only triggered via API/Telegram
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
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


class Scheduler:
    """Periodically checks for agents that need to run."""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # seconds between schedule checks
        self.runner = AgentRunner()

    async def run(self):
        """Main scheduler loop."""
        logger.info("Scheduler started")
        # Wait before first check to let the app fully start
        await asyncio.sleep(self.check_interval)
        while True:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(self.check_interval)

    async def _check_schedules(self):
        """Check all agents for due schedules."""
        async with async_session() as db:
            result = await db.execute(
                select(AgentConfig).where(
                    AgentConfig.status == AgentStatus.IDLE,
                    AgentConfig.schedule_type == "interval",
                    AgentConfig.schedule_value.isnot(None),
                )
            )
            agents = result.scalars().all()
            now = datetime.now(timezone.utc)

            for agent in agents:
                interval = parse_interval(agent.schedule_value)
                if not interval:
                    continue

                # Check if enough time has passed since last run
                if agent.last_run_at:
                    next_run = agent.last_run_at + interval
                    if now < next_run:
                        continue

                logger.info(f"Scheduling agent: {agent.name} (interval: {agent.schedule_value})")
                try:
                    await self.runner.start_run(agent, trigger="schedule", db=db)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to run agent {agent.name}: {e}")
                    await db.rollback()
