"""Agent Memory — persistent context that survives across runs."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentMemory, AgentConfig

router = APIRouter()


class MemoryWrite(BaseModel):
    key: str
    value: str
    memory_type: str = "general"


@router.get("/{agent_id}/memory")
async def list_memories(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id == agent_id).order_by(AgentMemory.updated_at.desc())
    )
    return [
        {"id": str(m.id), "key": m.key, "value": m.value, "memory_type": m.memory_type,
         "created_at": m.created_at.isoformat(), "updated_at": m.updated_at.isoformat()}
        for m in result.scalars().all()
    ]


@router.post("/{agent_id}/memory")
async def upsert_memory(agent_id: UUID, data: MemoryWrite, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Upsert: find existing by agent_id + key
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id == agent_id, AgentMemory.key == data.key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = data.value
        existing.memory_type = data.memory_type
        await db.flush()
        return {"id": str(existing.id), "updated": True}
    else:
        mem = AgentMemory(agent_id=agent_id, key=data.key, value=data.value, memory_type=data.memory_type)
        db.add(mem)
        await db.flush()
        return {"id": str(mem.id), "created": True}


@router.delete("/{agent_id}/memory/{key}")
async def delete_memory(agent_id: UUID, key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id == agent_id, AgentMemory.key == key)
    )
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    await db.delete(mem)
    return {"deleted": True}
