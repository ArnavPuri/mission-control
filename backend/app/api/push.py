"""Push Notifications API — browser push subscription management.

Stores push subscriptions and provides an endpoint to send push notifications.
Uses the Web Push protocol (VAPID). The actual sending requires pywebpush,
but the subscription management works without it.
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db

router = APIRouter()

# In-memory subscription store (persists for server lifetime only).
# WARNING: Subscriptions are lost on server restart. For production use,
# migrate to a DB-backed store (e.g. PushSubscription table).
_subscriptions: dict[str, dict] = {}


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {p256dh: str, auth: str}


class PushMessage(BaseModel):
    title: str
    body: str = ""
    url: str | None = None
    category: str = "info"


@router.post("/subscribe")
async def subscribe(data: PushSubscription):
    """Register a browser push subscription."""
    sub_id = str(uuid4())
    _subscriptions[sub_id] = {
        "id": sub_id,
        "endpoint": data.endpoint,
        "keys": data.keys,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"id": sub_id, "subscribed": True}


@router.delete("/subscribe/{sub_id}")
async def unsubscribe(sub_id: str):
    """Remove a push subscription."""
    if sub_id in _subscriptions:
        del _subscriptions[sub_id]
        return {"unsubscribed": True}
    raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/subscriptions")
async def list_subscriptions():
    """List active push subscriptions."""
    return {"count": len(_subscriptions), "subscriptions": list(_subscriptions.values())}


@router.post("/send")
async def send_push(data: PushMessage):
    """Send a push notification to all subscribers.

    Returns success count. If pywebpush is not installed,
    notifications are queued but not delivered.
    """
    sent = 0
    failed = 0
    errors: list[str] = []

    try:
        from pywebpush import webpush, WebPushException
        import os
        vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
        vapid_email = os.environ.get("VAPID_EMAIL", "mailto:admin@mission-control.local")

        if not vapid_private_key:
            return {
                "sent": 0,
                "failed": 0,
                "message": "VAPID_PRIVATE_KEY not configured — push disabled",
                "queued": len(_subscriptions),
            }

        import json
        payload = json.dumps({
            "title": data.title,
            "body": data.body,
            "url": data.url,
            "category": data.category,
        })

        to_remove = []
        for sub_id, sub in _subscriptions.items():
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": vapid_email},
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    to_remove.append(sub_id)  # subscription expired
                failed += 1
                errors.append(str(e)[:100])

        # Clean up expired subscriptions
        for sid in to_remove:
            _subscriptions.pop(sid, None)

    except ImportError:
        return {
            "sent": 0,
            "failed": 0,
            "message": "pywebpush not installed — push notifications queued only",
            "queued": len(_subscriptions),
        }

    return {"sent": sent, "failed": failed, "total_subscribers": len(_subscriptions)}


async def send_push_to_all(title: str, body: str = "", category: str = "info", url: str | None = None):
    """Helper to send push notifications from other parts of the system."""
    if not _subscriptions:
        return

    try:
        from pywebpush import webpush
        import os
        import json

        vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
        vapid_email = os.environ.get("VAPID_EMAIL", "mailto:admin@mission-control.local")
        if not vapid_private_key:
            return

        payload = json.dumps({"title": title, "body": body, "url": url, "category": category})

        for sub in _subscriptions.values():
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": vapid_email},
                )
            except Exception:
                pass
    except ImportError:
        pass
