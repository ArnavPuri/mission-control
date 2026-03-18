"""Agent Memory — persistent context that survives across runs.

Supports both per-agent memory and a shared scratchpad (agent_id=NULL)
for inter-agent collaboration.
"""

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


def _serialize(m: AgentMemory) -> dict:
    return {
        "id": str(m.id),
        "agent_id": str(m.agent_id) if m.agent_id else None,
        "key": m.key,
        "value": m.value,
        "memory_type": m.memory_type,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


# --- Shared scratchpad (agent_id=NULL, visible to all agents) ---

@router.get("/shared/memory")
async def list_shared_memories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id.is_(None)).order_by(AgentMemory.updated_at.desc())
    )
    return [_serialize(m) for m in result.scalars().all()]


@router.post("/shared/memory")
async def upsert_shared_memory(data: MemoryWrite, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id.is_(None), AgentMemory.key == data.key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = data.value
        existing.memory_type = data.memory_type
        await db.flush()
        return {"id": str(existing.id), "updated": True}
    else:
        mem = AgentMemory(agent_id=None, key=data.key, value=data.value, memory_type=data.memory_type or "shared")
        db.add(mem)
        await db.flush()
        return {"id": str(mem.id), "created": True}


@router.delete("/shared/memory/{key}")
async def delete_shared_memory(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id.is_(None), AgentMemory.key == key)
    )
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Shared memory entry not found")
    await db.delete(mem)
    return {"deleted": True}


# --- Per-agent memory ---

@router.get("/{agent_id}/memory")
async def list_memories(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory).where(AgentMemory.agent_id == agent_id).order_by(AgentMemory.updated_at.desc())
    )
    return [_serialize(m) for m in result.scalars().all()]


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
