"""
Todoist Integration for Mission Control.

Bidirectional sync between Todoist tasks and MC tasks.
Receive Todoist webhooks for real-time updates.
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

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Constants ───

TODOIST_API_BASE = "https://api.todoist.com/rest/v2"

# Priority mapping: Todoist (1=normal, 4=urgent) -> MC
TODOIST_PRIORITY_TO_MC = {
    1: TaskPriority.LOW,
    2: TaskPriority.MEDIUM,
    3: TaskPriority.HIGH,
    4: TaskPriority.CRITICAL,
}

MC_PRIORITY_TO_TODOIST = {
    TaskPriority.LOW: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.HIGH: 3,
    TaskPriority.CRITICAL: 4,
}


# ─── Schemas ───

class TodoistConnect(BaseModel):
    api_key: str


# ─── Helpers ───

def _require_todoist():
    """Raise 503 if Todoist API key is not configured."""
    if not settings.todoist_api_key:
        raise HTTPException(status_code=503, detail="Todoist API key not configured. POST /api/todoist/connect first.")


def _todoist_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


# ─── Connect ───

@router.post("/connect")
async def connect_todoist(data: TodoistConnect):
    """Save and validate Todoist API token."""
    import httpx

    headers = _todoist_headers(data.api_key)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TODOIST_API_BASE}/projects", headers=headers)
        if resp.status_code == 403:
            raise HTTPException(status_code=400, detail="Invalid Todoist API token")
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Todoist API error: {resp.status_code}")
        projects = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Todoist API: {e}")

    settings.todoist_api_key = data.api_key
    logger.info(f"Todoist connected successfully ({len(projects)} projects)")
    return {"connected": True, "projects": len(projects)}


# ─── List Projects ───

@router.get("/projects")
async def list_projects():
    """List Todoist projects."""
    import httpx

    _require_todoist()
    headers = _todoist_headers(settings.todoist_api_key)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TODOIST_API_BASE}/projects", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Todoist API error")
        projects = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Todoist API error: {e}")

    return [
        {
            "id": p["id"],
            "name": p["name"],
            "color": p.get("color"),
            "is_favorite": p.get("is_favorite", False),
        }
        for p in projects
    ]


# ─── Sync ───

@router.post("/sync")
async def sync_todoist(
    project_id: str | None = None,
    mc_project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Bidirectional sync between Todoist and MC tasks.

    - Fetches active Todoist tasks, creates/updates MC tasks with todoist_id tag.
    - Pushes MC task completions back to Todoist.
    """
    import httpx

    _require_todoist()
    headers = _todoist_headers(settings.todoist_api_key)

    # --- Pull from Todoist ---
    params = {}
    if project_id:
        params["project_id"] = project_id

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{TODOIST_API_BASE}/tasks", headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Todoist API error: {resp.text}")
        todoist_tasks = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Todoist API error: {e}")

    created = 0
    updated = 0
    mc_proj_id = UUID(mc_project_id) if mc_project_id else None

    for tt in todoist_tasks:
        todoist_id = str(tt["id"])
        content = tt.get("content", "")
        priority = tt.get("priority", 1)
        is_completed = tt.get("is_completed", False)
        due = tt.get("due")

        todoist_tag = f"todoist:{todoist_id}"
        mc_priority = TODOIST_PRIORITY_TO_MC.get(priority, TaskPriority.MEDIUM)
        mc_status = TaskStatus.DONE if is_completed else TaskStatus.TODO

        # Parse due date
        due_date = None
        if due and due.get("date"):
            try:
                due_str = due["date"]
                if "T" in due_str:
                    due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                else:
                    due_date = datetime.strptime(due_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        # Check if task exists
        existing = await db.execute(select(Task).where(Task.tags.any(todoist_tag)))
        task = existing.scalar_one_or_none()

        if task:
            task.text = content
            task.priority = mc_priority
            task.status = mc_status
            task.due_date = due_date
            updated += 1
        else:
            labels = tt.get("labels", [])
            task = Task(
                text=content,
                status=mc_status,
                priority=mc_priority,
                source="todoist",
                tags=[todoist_tag] + [f"label:{l}" for l in labels],
                due_date=due_date,
                project_id=mc_proj_id,
            )
            db.add(task)
            created += 1

    # --- Push completed MC tasks back to Todoist ---
    pushed = 0
    result = await db.execute(
        select(Task).where(
            Task.source == "todoist",
            Task.status == TaskStatus.DONE,
        )
    )
    done_tasks = result.scalars().all()

    async with httpx.AsyncClient(timeout=10) as client:
        for task in done_tasks:
            if not task.tags:
                continue
            todoist_ids = [t.split(":", 1)[1] for t in task.tags if t.startswith("todoist:")]
            for tid in todoist_ids:
                try:
                    resp = await client.post(
                        f"{TODOIST_API_BASE}/tasks/{tid}/close",
                        headers=headers,
                    )
                    if resp.status_code in (200, 204):
                        pushed += 1
                except Exception as e:
                    logger.error(f"Todoist close task {tid} failed: {e}")

    # Log the sync
    db.add(EventLog(
        event_type="todoist.synced",
        entity_type="integration",
        source="todoist",
        data={"created": created, "updated": updated, "pushed_completions": pushed, "total": len(todoist_tasks)},
    ))
    await db.flush()

    logger.info(f"Todoist sync complete: {created} created, {updated} updated, {pushed} pushed")
    return {
        "synced": True,
        "created": created,
        "updated": updated,
        "pushed_completions": pushed,
        "total_todoist_tasks": len(todoist_tasks),
    }


# ─── Webhook Receiver ───

@router.post("/webhook")
async def todoist_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Todoist webhook events.

    Todoist sends webhooks for task creation, completion, updates, etc.
    See: https://developer.todoist.com/sync/v9/#webhooks
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_name = payload.get("event_name", "")
    event_data = payload.get("event_data", {})

    todoist_id = str(event_data.get("id", ""))
    content = event_data.get("content", "")
    priority = event_data.get("priority", 1)

    if not todoist_id:
        return {"received": True, "skipped": True}

    todoist_tag = f"todoist:{todoist_id}"

    # Find existing task
    existing = await db.execute(select(Task).where(Task.tags.any(todoist_tag)))
    task = existing.scalar_one_or_none()

    if event_name == "item:added":
        if not task:
            mc_priority = TODOIST_PRIORITY_TO_MC.get(priority, TaskPriority.MEDIUM)
            task = Task(
                text=content,
                status=TaskStatus.TODO,
                priority=mc_priority,
                source="todoist",
                tags=[todoist_tag],
            )
            db.add(task)
            db.add(EventLog(
                event_type="task.created",
                entity_type="task",
                source="todoist",
                data={"content": content, "todoist_id": todoist_id},
            ))
            await db.flush()
            await broadcast("task.created", {"id": str(task.id), "text": task.text, "source": "todoist"})

    elif event_name == "item:updated" and task:
        if content:
            task.text = content
        mc_priority = TODOIST_PRIORITY_TO_MC.get(priority)
        if mc_priority:
            task.priority = mc_priority
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="todoist",
            data={"event": "updated", "todoist_id": todoist_id},
        ))
        await db.flush()
        await broadcast("task.updated", {"id": str(task.id), "text": task.text, "source": "todoist"})

    elif event_name == "item:completed" and task:
        task.status = TaskStatus.DONE
        task.completed_at = datetime.now(timezone.utc)
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="todoist",
            data={"event": "completed", "todoist_id": todoist_id},
        ))
        await db.flush()
        await broadcast("task.updated", {"id": str(task.id), "text": task.text, "status": "done", "source": "todoist"})

    elif event_name == "item:uncompleted" and task:
        task.status = TaskStatus.TODO
        task.completed_at = None
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="todoist",
            data={"event": "uncompleted", "todoist_id": todoist_id},
        ))
        await db.flush()
        await broadcast("task.updated", {"id": str(task.id), "text": task.text, "status": "todo", "source": "todoist"})

    elif event_name == "item:deleted" and task:
        task.status = TaskStatus.DONE
        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="todoist",
            data={"event": "deleted_in_todoist", "todoist_id": todoist_id},
        ))
        await db.flush()

    return {"received": True, "event": event_name}
