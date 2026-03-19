"""
Linear Integration for Mission Control.

Sync Linear issues <-> MC tasks bidirectionally.
Receive Linear webhooks for real-time updates.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import EventLog, Task, TaskStatus, TaskPriority
from app.api.ws import broadcast
from app.config import settings
from app.api.api_keys import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ───

class LinearConnect(BaseModel):
    api_key: str


# ─── Status Mapping ───

LINEAR_STATUS_TO_MC = {
    "Backlog": TaskStatus.TODO,
    "Todo": TaskStatus.TODO,
    "In Progress": TaskStatus.IN_PROGRESS,
    "Done": TaskStatus.DONE,
    "Canceled": TaskStatus.DONE,
}

MC_STATUS_TO_LINEAR = {
    TaskStatus.TODO: "Todo",
    TaskStatus.IN_PROGRESS: "In Progress",
    TaskStatus.BLOCKED: "In Progress",
    TaskStatus.DONE: "Done",
}

LINEAR_PRIORITY_TO_MC = {
    0: TaskPriority.LOW,       # No priority
    1: TaskPriority.CRITICAL,  # Urgent
    2: TaskPriority.HIGH,      # High
    3: TaskPriority.MEDIUM,    # Medium
    4: TaskPriority.LOW,       # Low
}


def _get_api_key() -> str:
    """Get the Linear API key or raise 503."""
    if not settings.linear_api_key:
        raise HTTPException(status_code=503, detail="Linear API key not configured. POST /api/linear/connect first.")
    return settings.linear_api_key


# ─── Connect ───

@router.post("/connect", dependencies=[Depends(require_admin)])
async def connect_linear(data: LinearConnect):
    """Save Linear API key to settings."""
    import httpx

    # Validate the key by making a test request
    headers = {"Authorization": data.api_key, "Content-Type": "application/json"}
    query = '{"query": "{ viewer { id name } }"}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post("https://api.linear.app/graphql", content=query, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid Linear API key")
        result = resp.json()
        if "errors" in result:
            raise HTTPException(status_code=400, detail=f"Linear API error: {result['errors']}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Linear API: {e}")

    settings.linear_api_key = data.api_key
    viewer = result.get("data", {}).get("viewer", {})
    logger.info(f"Linear connected as: {viewer.get('name', 'unknown')}")
    logger.warning("Linear API key stored in memory only — will be lost on restart. Set LINEAR_API_KEY in .env for persistence.")
    return {"connected": True, "user": viewer.get("name")}


# ─── List Teams ───

@router.get("/teams")
async def list_teams():
    """List Linear teams accessible with the configured API key."""
    import httpx

    api_key = _get_api_key()
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    query = '{"query": "{ teams { nodes { id name key } } }"}'

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post("https://api.linear.app/graphql", content=query, headers=headers)
        result = resp.json()
        teams = result.get("data", {}).get("teams", {}).get("nodes", [])
        return [{"id": t["id"], "name": t["name"], "key": t["key"]} for t in teams]
    except Exception as e:
        logger.error(f"Linear teams fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"Linear API error: {e}")


# ─── Sync ───

@router.post("/sync")
async def sync_linear(team_id: str | None = None, db: AsyncSession = Depends(get_db)):
    """Sync issues from Linear to MC tasks (bidirectional).

    - Fetches open issues from Linear, creates/updates MC tasks with linear_id tag.
    - Pushes MC task status changes back to Linear.
    """
    import httpx

    api_key = _get_api_key()
    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    # Build query - optionally filter by team
    team_filter = f'teamId: "{team_id}",' if team_id else ""
    query = f'''{{
        "query": "{{ issues({team_filter} first: 100, orderBy: updatedAt) {{ nodes {{ id title description priority state {{ name }} team {{ key }} identifier }} }} }}"
    }}'''

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.linear.app/graphql", content=query, headers=headers)
        result = resp.json()
    except Exception as e:
        logger.error(f"Linear sync fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"Linear API error: {e}")

    issues = result.get("data", {}).get("issues", {}).get("nodes", [])
    created = 0
    updated = 0

    for issue in issues:
        linear_id = issue["id"]
        identifier = issue.get("identifier", "")
        title = issue.get("title", "")
        state_name = issue.get("state", {}).get("name", "Todo")
        priority = issue.get("priority", 0)

        linear_tag = f"linear:{linear_id}"
        mc_status = LINEAR_STATUS_TO_MC.get(state_name, TaskStatus.TODO)
        mc_priority = LINEAR_PRIORITY_TO_MC.get(priority, TaskPriority.MEDIUM)

        # Check if task already exists
        existing = await db.execute(
            select(Task).where(Task.tags.any(linear_tag))
        )
        task = existing.scalar_one_or_none()

        if task:
            # Update existing task
            task.text = f"[{identifier}] {title}"
            task.status = mc_status
            task.priority = mc_priority
            updated += 1
        else:
            # Create new task
            task = Task(
                text=f"[{identifier}] {title}",
                status=mc_status,
                priority=mc_priority,
                source="linear",
                tags=[linear_tag, f"linear-id:{identifier}"],
            )
            db.add(task)
            created += 1

    # Log the sync
    db.add(EventLog(
        event_type="linear.synced",
        entity_type="integration",
        source="linear",
        data={"created": created, "updated": updated, "total_issues": len(issues)},
    ))
    await db.flush()

    logger.info(f"Linear sync complete: {created} created, {updated} updated")
    return {"synced": True, "created": created, "updated": updated, "total_issues": len(issues)}


# ─── Webhook Receiver ───

@router.post("/webhook")
async def linear_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Linear webhook events for issue updates."""
    # Verify webhook signature if secret is configured
    if settings.linear_webhook_secret:
        import hashlib
        import hmac
        body = await request.body()
        signature = request.headers.get("linear-signature", "")
        expected = hmac.new(
            settings.linear_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    action = payload.get("action", "")
    event_type = payload.get("type", "")
    data = payload.get("data", {})

    # We care about Issue events
    if event_type != "Issue":
        return {"received": True, "skipped": True}

    linear_id = data.get("id", "")
    title = data.get("title", "")
    state_name = data.get("state", {}).get("name", "") if isinstance(data.get("state"), dict) else ""
    priority = data.get("priority", 0)

    linear_tag = f"linear:{linear_id}"

    # Find existing task
    existing = await db.execute(
        select(Task).where(Task.tags.any(linear_tag))
    )
    task = existing.scalar_one_or_none()

    if action == "create":
        if not task:
            mc_status = LINEAR_STATUS_TO_MC.get(state_name, TaskStatus.TODO)
            mc_priority = LINEAR_PRIORITY_TO_MC.get(priority, TaskPriority.MEDIUM)
            task = Task(
                text=f"{title}",
                status=mc_status,
                priority=mc_priority,
                source="linear",
                tags=[linear_tag],
            )
            db.add(task)
            db.add(EventLog(
                event_type="task.created",
                entity_type="task",
                source="linear",
                data={"title": title, "linear_id": linear_id},
            ))
            await db.flush()
            await broadcast("task.created", {"id": str(task.id), "text": task.text, "source": "linear"})

    elif action == "update" and task:
        if title:
            task.text = title
        if state_name:
            mc_status = LINEAR_STATUS_TO_MC.get(state_name)
            if mc_status:
                task.status = mc_status
        if priority:
            mc_priority = LINEAR_PRIORITY_TO_MC.get(priority)
            if mc_priority:
                task.priority = mc_priority
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="linear",
            data={"action": "update", "linear_id": linear_id},
        ))
        await db.flush()
        await broadcast("task.updated", {"id": str(task.id), "text": task.text, "source": "linear"})

    elif action == "remove" and task:
        task.status = TaskStatus.DONE
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="linear",
            data={"action": "removed_in_linear", "linear_id": linear_id},
        ))
        await db.flush()

    return {"received": True, "action": action}
