"""
Zapier/Make Generic Webhook Integration for Mission Control.

Provides:
- Outbound webhook registration (fire when MC events occur)
- Inbound action endpoint (Zapier/Make sends actions to MC)
- Zapier subscription/test endpoints for trigger discovery
"""

import hashlib
import hmac
import json
import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import EventLog, Task, Idea, Note, TaskStatus, TaskPriority
from app.api.ws import broadcast

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── In-memory hook store (for Zapier/Make webhook subscriptions) ───
# In production, these would go in the database. For now, kept in memory
# alongside the existing WebhookConfig system.
_zapier_hooks: dict[str, dict] = {}


# ─── Schemas ───

class ZapierHookCreate(BaseModel):
    name: str
    events: list[str]  # e.g. ["task.created", "task.updated", "idea.created"]
    url: str
    secret: str | None = None


class InboundAction(BaseModel):
    action: str  # create_task, create_idea, create_note
    data: dict


# ─── Available triggers/events ───

AVAILABLE_TRIGGERS = [
    {"key": "task.created", "label": "Task Created", "description": "Fires when a new task is created"},
    {"key": "task.updated", "label": "Task Updated", "description": "Fires when a task is updated"},
    {"key": "task.completed", "label": "Task Completed", "description": "Fires when a task is marked done"},
    {"key": "idea.created", "label": "Idea Created", "description": "Fires when a new idea is added"},
    {"key": "note.created", "label": "Note Created", "description": "Fires when a new note is created"},
    {"key": "agent.completed", "label": "Agent Run Completed", "description": "Fires when an agent finishes a run"},
]

SAMPLE_DATA = {
    "task.created": {
        "id": "sample-uuid-1234",
        "text": "Sample task from Mission Control",
        "status": "todo",
        "priority": "medium",
        "source": "manual",
        "created_at": "2026-01-01T00:00:00Z",
    },
    "idea.created": {
        "id": "sample-uuid-5678",
        "text": "Sample idea from Mission Control",
        "source": "manual",
        "created_at": "2026-01-01T00:00:00Z",
    },
    "note.created": {
        "id": "sample-uuid-9012",
        "title": "Sample Note",
        "content": "This is a sample note.",
        "tags": ["sample"],
        "created_at": "2026-01-01T00:00:00Z",
    },
}


# ─── Hook Management ───

@router.post("/hooks")
async def register_hook(data: ZapierHookCreate):
    """Register a Zapier/Make webhook to receive outbound events."""
    hook_id = str(uuid4())
    _zapier_hooks[hook_id] = {
        "id": hook_id,
        "name": data.name,
        "events": data.events,
        "url": data.url,
        "secret": data.secret,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"Zapier hook registered: {data.name} -> {data.url} (events: {data.events})")
    return {"id": hook_id, "name": data.name, "events": data.events}


@router.get("/hooks")
async def list_hooks():
    """List all registered Zapier/Make webhooks."""
    return list(_zapier_hooks.values())


@router.delete("/hooks/{hook_id}")
async def remove_hook(hook_id: str):
    """Remove a registered Zapier/Make webhook."""
    if hook_id not in _zapier_hooks:
        raise HTTPException(status_code=404, detail="Hook not found")
    removed = _zapier_hooks.pop(hook_id)
    logger.info(f"Zapier hook removed: {removed['name']}")
    return {"deleted": True, "id": hook_id}


# ─── Inbound Actions ───

@router.post("/inbound")
async def inbound_action(data: InboundAction, db: AsyncSession = Depends(get_db)):
    """Accept inbound actions from Zapier/Make (create task, idea, note, etc.)."""
    action = data.action
    payload = data.data

    if action == "create_task":
        task = Task(
            text=payload.get("text", "Untitled task"),
            status=TaskStatus(payload.get("status", "todo")),
            priority=TaskPriority(payload.get("priority", "medium")),
            source="zapier",
            tags=payload.get("tags", []),
        )
        db.add(task)
        await db.flush()

        db.add(EventLog(
            event_type="task.created",
            entity_type="task",
            entity_id=task.id,
            source="zapier",
            data={"text": task.text},
        ))
        await db.flush()
        await broadcast("task.created", {"id": str(task.id), "text": task.text})
        return {"created": "task", "id": str(task.id)}

    elif action == "create_idea":
        idea = Idea(
            text=payload.get("text", "Untitled idea"),
            source="zapier",
            tags=payload.get("tags", []),
        )
        db.add(idea)
        await db.flush()

        db.add(EventLog(
            event_type="idea.created",
            entity_type="idea",
            entity_id=idea.id,
            source="zapier",
            data={"text": idea.text},
        ))
        await db.flush()
        await broadcast("idea.created", {"id": str(idea.id), "text": idea.text})
        return {"created": "idea", "id": str(idea.id)}

    elif action == "create_note":
        note = Note(
            title=payload.get("title", "Untitled note"),
            content=payload.get("content", ""),
            source="zapier",
            tags=payload.get("tags", []),
        )
        db.add(note)
        await db.flush()

        db.add(EventLog(
            event_type="note.created",
            entity_type="note",
            entity_id=note.id,
            source="zapier",
            data={"title": note.title},
        ))
        await db.flush()
        await broadcast("note.created", {"id": str(note.id), "title": note.title})
        return {"created": "note", "id": str(note.id)}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}. Supported: create_task, create_idea, create_note")


# ─── Zapier Subscription Endpoint ───

@router.get("/subscribe")
async def zapier_subscribe():
    """Zapier subscription endpoint - returns available triggers."""
    return AVAILABLE_TRIGGERS


# ─── Zapier Test Trigger ───

@router.post("/test")
async def zapier_test(event_type: str = "task.created"):
    """Zapier test trigger - returns sample data for the given event type."""
    sample = SAMPLE_DATA.get(event_type)
    if not sample:
        sample = SAMPLE_DATA["task.created"]
    return [sample]


# ─── Outbound Dispatcher ───

async def dispatch_zapier_hooks(event_type: str, data: dict):
    """Fire all registered Zapier/Make webhooks matching the event type.

    Called from other parts of the system when events occur.
    Hook into EventLog broadcast to trigger this.
    """
    import httpx

    matching = [
        h for h in _zapier_hooks.values()
        if event_type in h["events"]
        or any(event_type.startswith(e.rstrip("*")) for e in h["events"] if e.endswith("*"))
    ]

    if not matching:
        return

    payload = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "mission-control",
    }

    for hook in matching:
        try:
            headers = {"Content-Type": "application/json"}
            if hook.get("secret"):
                body_bytes = json.dumps(payload).encode()
                sig = hmac.new(hook["secret"].encode(), body_bytes, hashlib.sha256).hexdigest()
                headers["x-webhook-signature"] = sig

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(hook["url"], json=payload, headers=headers)
            logger.info(f"Zapier hook {hook['name']} fired: {resp.status_code}")
        except Exception as e:
            logger.error(f"Zapier hook {hook['name']} failed: {e}")
