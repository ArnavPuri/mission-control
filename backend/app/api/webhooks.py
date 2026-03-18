"""
Webhook system for Mission Control.

Inbound: Accept events from external services (GitHub, Stripe, etc.)
Outbound: Notify external services when events happen in MC.
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import hashlib
import hmac
import json
import logging
import httpx

from app.db.session import get_db
from app.db.models import EventLog, WebhookConfig, WebhookLog
from app.api.ws import broadcast

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ───

class WebhookCreate(BaseModel):
    name: str
    direction: str  # "inbound" or "outbound"
    url: str | None = None
    secret: str | None = None
    events: list[str] = []
    headers: dict = {}


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    headers: dict | None = None
    is_active: bool | None = None


# ─── Webhook Management ───

@router.get("")
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebhookConfig).order_by(WebhookConfig.created_at.desc()))
    hooks = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "name": h.name,
            "direction": h.direction,
            "url": h.url,
            "events": h.events or [],
            "is_active": h.is_active,
            "trigger_count": h.trigger_count,
            "last_triggered_at": h.last_triggered_at.isoformat() if h.last_triggered_at else None,
            "created_at": h.created_at.isoformat(),
        }
        for h in hooks
    ]


@router.post("")
async def create_webhook(data: WebhookCreate, db: AsyncSession = Depends(get_db)):
    if data.direction not in ("inbound", "outbound"):
        raise HTTPException(status_code=400, detail="direction must be 'inbound' or 'outbound'")
    if data.direction == "outbound" and not data.url:
        raise HTTPException(status_code=400, detail="outbound webhooks require a url")

    # Generate a secret for inbound webhooks if not provided
    secret = data.secret
    if data.direction == "inbound" and not secret:
        secret = hashlib.sha256(_uuid.uuid4().bytes).hexdigest()[:32]

    hook = WebhookConfig(
        name=data.name,
        direction=data.direction,
        url=data.url,
        secret=secret,
        events=data.events,
        headers=data.headers,
    )
    db.add(hook)
    await db.flush()

    result = {"id": str(hook.id), "name": hook.name, "direction": hook.direction}
    if data.direction == "inbound":
        result["endpoint"] = f"/api/webhooks/in/{hook.id}"
        result["secret"] = secret
    return result


@router.patch("/{webhook_id}")
async def update_webhook(webhook_id: UUID, data: WebhookUpdate, db: AsyncSession = Depends(get_db)):
    hook = await db.get(WebhookConfig, webhook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(hook, key, val)
    await db.flush()
    return {"id": str(hook.id), "updated": True}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: UUID, db: AsyncSession = Depends(get_db)):
    hook = await db.get(WebhookConfig, webhook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(hook)
    return {"deleted": True}


@router.get("/{webhook_id}/logs")
async def list_webhook_logs(webhook_id: UUID, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WebhookLog)
        .where(WebhookLog.webhook_id == webhook_id)
        .order_by(desc(WebhookLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "event_type": l.event_type,
            "success": l.success,
            "status_code": l.status_code,
            "payload_preview": json.dumps(l.payload)[:200] if l.payload else None,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


# ─── Inbound Webhook Receiver ───

@router.post("/in/{webhook_id}")
async def receive_webhook(webhook_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Receive an inbound webhook from an external service."""
    hook = await db.get(WebhookConfig, webhook_id)
    if not hook or hook.direction != "inbound" or not hook.is_active:
        raise HTTPException(status_code=404, detail="Webhook not found")

    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Verify signature if secret is set
    if hook.secret:
        signature = request.headers.get("x-webhook-signature", "")
        expected = hmac.new(hook.secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            log = WebhookLog(
                webhook_id=webhook_id, direction="inbound",
                event_type="auth_failed", payload=payload,
                success=False, status_code="401",
            )
            db.add(log)
            await db.flush()
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Determine event type from payload or headers
    event_type = (
        request.headers.get("x-event-type") or
        payload.get("event") or
        payload.get("type") or
        payload.get("action") or
        "webhook.received"
    )

    # Log the webhook
    log = WebhookLog(
        webhook_id=webhook_id, direction="inbound",
        event_type=event_type, payload=payload,
        success=True, status_code="200",
    )
    db.add(log)

    # Update webhook stats
    hook.last_triggered_at = datetime.now(timezone.utc)
    hook.trigger_count = (hook.trigger_count or 0) + 1

    # Create event log entry
    event = EventLog(
        event_type=f"webhook.{event_type}",
        entity_type="webhook",
        entity_id=webhook_id,
        source=f"webhook:{hook.name}",
        data=payload,
    )
    db.add(event)
    await db.flush()

    # Broadcast to dashboard
    await broadcast("webhook.received", {
        "webhook_id": str(webhook_id),
        "webhook_name": hook.name,
        "event_type": event_type,
    })

    return {"received": True, "event_type": event_type}


# ─── Outbound Webhook Dispatcher ───

async def dispatch_outbound_webhooks(event_type: str, data: dict, db: AsyncSession):
    """Send outbound webhooks for a given event type.

    Called from other parts of the system when events occur.
    """
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.direction == "outbound",
            WebhookConfig.is_active == True,
        )
    )
    hooks = result.scalars().all()

    for hook in hooks:
        # Check if this hook subscribes to this event type
        if hook.events and event_type not in hook.events:
            # Also check wildcards (e.g., "task.*" matches "task.created")
            if not any(
                event_type.startswith(e.rstrip("*")) for e in hook.events if e.endswith("*")
            ):
                continue

        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "mission-control",
        }

        try:
            headers = {"Content-Type": "application/json", **(hook.headers or {})}

            # Add signature if secret is set
            if hook.secret:
                body_bytes = json.dumps(payload).encode()
                sig = hmac.new(hook.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
                headers["x-webhook-signature"] = sig

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(hook.url, json=payload, headers=headers)

            log = WebhookLog(
                webhook_id=hook.id, direction="outbound",
                event_type=event_type, payload=payload,
                success=resp.is_success,
                status_code=str(resp.status_code),
                response_body=resp.text[:500] if resp.text else None,
            )
            db.add(log)

            hook.last_triggered_at = datetime.now(timezone.utc)
            hook.trigger_count = (hook.trigger_count or 0) + 1

        except Exception as e:
            logger.error(f"Outbound webhook {hook.name} failed: {e}")
            log = WebhookLog(
                webhook_id=hook.id, direction="outbound",
                event_type=event_type, payload=payload,
                success=False, status_code="error",
                response_body=str(e)[:500],
            )
            db.add(log)

    await db.flush()
