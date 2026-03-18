"""Conditional Triggers — run agents when DB conditions are met."""

import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentTrigger, AgentConfig, AgentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class TriggerCreate(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    entity_type: str  # task, idea, goal, habit, journal
    event: str  # created, updated, status_changed, completed
    condition: dict | None = None  # {"field": "priority", "op": "eq", "value": "critical"}


class TriggerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    entity_type: str | None = None
    event: str | None = None
    condition: dict | None = None


def _serialize(t: AgentTrigger) -> dict:
    return {
        "id": str(t.id),
        "agent_id": str(t.agent_id),
        "agent_name": t.agent.name if t.agent else None,
        "name": t.name,
        "description": t.description,
        "is_active": t.is_active,
        "entity_type": t.entity_type,
        "event": t.event,
        "condition": t.condition,
        "last_triggered_at": t.last_triggered_at.isoformat() if t.last_triggered_at else None,
        "trigger_count": t.trigger_count,
        "created_at": t.created_at.isoformat(),
    }


@router.get("")
async def list_triggers(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(AgentTrigger).order_by(AgentTrigger.created_at.desc())
    if active_only:
        query = query.where(AgentTrigger.is_active == True)
    result = await db.execute(query)
    return [_serialize(t) for t in result.scalars().all()]


@router.post("")
async def create_trigger(data: TriggerCreate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, UUID(data.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    trigger = AgentTrigger(
        agent_id=UUID(data.agent_id),
        name=data.name,
        description=data.description,
        entity_type=data.entity_type,
        event=data.event,
        condition=data.condition,
    )
    db.add(trigger)
    await db.flush()
    return {"id": str(trigger.id), "name": trigger.name}


@router.patch("/{trigger_id}")
async def update_trigger(trigger_id: UUID, data: TriggerUpdate, db: AsyncSession = Depends(get_db)):
    trigger = await db.get(AgentTrigger, trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(trigger, key, val)
    await db.flush()
    return {"updated": True}


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: UUID, db: AsyncSession = Depends(get_db)):
    trigger = await db.get(AgentTrigger, trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await db.delete(trigger)
    return {"deleted": True}


async def evaluate_triggers(entity_type: str, event: str, entity_data: dict, db: AsyncSession):
    """Check all active triggers and fire matching ones.

    Called from action handlers (task create, idea create, etc.)
    """
    result = await db.execute(
        select(AgentTrigger).where(
            AgentTrigger.is_active == True,
            AgentTrigger.entity_type == entity_type,
            AgentTrigger.event == event,
        )
    )
    triggers = result.scalars().all()

    for trigger in triggers:
        if not _matches_condition(trigger.condition, entity_data):
            continue

        agent = await db.get(AgentConfig, trigger.agent_id)
        if not agent or agent.status == AgentStatus.RUNNING:
            continue

        logger.info(f"Trigger fired: {trigger.name} -> {agent.name}")
        trigger.last_triggered_at = datetime.now(timezone.utc)
        trigger.trigger_count += 1
        await db.flush()

        # Fire the agent in background
        import asyncio
        from app.orchestrator.runner import AgentRunner
        runner = AgentRunner()

        async def _run(agent_id, trigger_name):
            from app.db.session import async_session
            async with async_session() as session:
                a = await session.get(AgentConfig, agent_id)
                if a:
                    await runner.start_run(a, trigger=f"trigger:{trigger_name}", db=session)
                    await session.commit()

        asyncio.create_task(_run(agent.id, trigger.name))


def _matches_condition(condition: dict | None, entity_data: dict) -> bool:
    """Evaluate a simple condition against entity data."""
    if not condition:
        return True  # No condition = always match

    field = condition.get("field")
    op = condition.get("op", "eq")
    value = condition.get("value")

    if not field or field not in entity_data:
        return False

    actual = entity_data[field]

    if op == "eq":
        return str(actual) == str(value)
    elif op == "neq":
        return str(actual) != str(value)
    elif op == "contains":
        return str(value).lower() in str(actual).lower()
    elif op == "gt":
        try:
            return float(actual) > float(value)
        except (ValueError, TypeError):
            return False
    elif op == "lt":
        try:
            return float(actual) < float(value)
        except (ValueError, TypeError):
            return False

    return False
