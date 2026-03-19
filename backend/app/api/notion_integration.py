"""
Notion Integration for Mission Control.

Import Notion databases as tasks/notes, export MC data to Notion.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import EventLog, Task, Note, TaskStatus, TaskPriority
from app.api.ws import broadcast
from app.config import settings
from app.api.api_keys import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Constants ───

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ─── Schemas ───

class NotionConnect(BaseModel):
    api_key: str


class NotionImport(BaseModel):
    database_id: str
    import_as: str = "tasks"  # "tasks" or "notes"
    project_id: str | None = None


class NotionExport(BaseModel):
    database_id: str
    export_type: str = "tasks"  # "tasks" or "notes"
    project_id: str | None = None


# ─── Helpers ───

def _require_notion():
    """Raise 503 if Notion API key is not configured."""
    if not settings.notion_api_key:
        raise HTTPException(status_code=503, detail="Notion API key not configured. POST /api/notion/connect first.")


def _notion_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _extract_title(properties: dict) -> str:
    """Extract a title string from Notion page properties."""
    for prop in properties.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in title_parts)
    return "Untitled"


def _extract_rich_text(properties: dict, key: str) -> str:
    """Extract rich text content from a Notion property."""
    prop = properties.get(key, {})
    if prop.get("type") == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts)
    return ""


def _extract_status(properties: dict) -> TaskStatus:
    """Try to map a Notion status/select to MC TaskStatus."""
    for prop in properties.values():
        if prop.get("type") == "status":
            name = (prop.get("status") or {}).get("name", "").lower()
            if name in ("done", "complete", "completed"):
                return TaskStatus.DONE
            elif name in ("in progress", "doing", "active"):
                return TaskStatus.IN_PROGRESS
            elif name in ("blocked",):
                return TaskStatus.BLOCKED
        elif prop.get("type") == "select":
            name = (prop.get("select") or {}).get("name", "").lower()
            if name in ("done", "complete", "completed"):
                return TaskStatus.DONE
            elif name in ("in progress", "doing"):
                return TaskStatus.IN_PROGRESS
    return TaskStatus.TODO


def _extract_tags(properties: dict) -> list[str]:
    """Extract multi-select values as tags."""
    tags = []
    for prop in properties.values():
        if prop.get("type") == "multi_select":
            for option in prop.get("multi_select", []):
                tags.append(option.get("name", ""))
    return tags


# ─── Connect ───

@router.post("/connect", dependencies=[Depends(require_admin)])
async def connect_notion(data: NotionConnect):
    """Save and validate Notion API key."""
    import httpx

    headers = _notion_headers(data.api_key)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NOTION_API_BASE}/users/me", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid Notion API key")
        result = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Notion API: {e}")

    settings.notion_api_key = data.api_key
    bot_name = result.get("name", "Unknown")
    logger.info(f"Notion connected as: {bot_name}")
    logger.warning("Notion API key stored in memory only — will be lost on restart. Set NOTION_API_KEY in .env for persistence.")
    return {"connected": True, "bot_name": bot_name}


# ─── List Databases ───

@router.get("/databases")
async def list_databases():
    """List accessible Notion databases."""
    import httpx

    _require_notion()
    headers = _notion_headers(settings.notion_api_key)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{NOTION_API_BASE}/search",
                json={"filter": {"value": "database", "property": "object"}},
                headers=headers,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Notion API error")
        result = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Notion API error: {e}")

    databases = result.get("results", [])
    return [
        {
            "id": db["id"],
            "title": db.get("title", [{}])[0].get("plain_text", "Untitled") if db.get("title") else "Untitled",
            "url": db.get("url"),
        }
        for db in databases
    ]


# ─── Import ───

@router.post("/import")
async def import_from_notion(data: NotionImport, db: AsyncSession = Depends(get_db)):
    """Import pages from a Notion database as tasks or notes."""
    import httpx

    _require_notion()
    headers = _notion_headers(settings.notion_api_key)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{NOTION_API_BASE}/databases/{data.database_id}/query",
                json={"page_size": 100},
                headers=headers,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to query Notion database: {resp.text}")
        result = resp.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Notion API error: {e}")

    pages = result.get("results", [])
    created = 0
    project_id = UUID(data.project_id) if data.project_id else None

    for page in pages:
        properties = page.get("properties", {})
        notion_id = page["id"]
        title = _extract_title(properties)
        notion_tag = f"notion:{notion_id}"

        if not title:
            continue

        if data.import_as == "tasks":
            # Skip if already imported
            existing = await db.execute(select(Task).where(Task.tags.any(notion_tag)))
            if existing.scalar_one_or_none():
                continue

            status = _extract_status(properties)
            tags = _extract_tags(properties) + [notion_tag]

            task = Task(
                text=title,
                status=status,
                source="notion",
                tags=tags,
                project_id=project_id,
            )
            db.add(task)
            created += 1

        elif data.import_as == "notes":
            # Skip if already imported
            existing = await db.execute(select(Note).where(Note.tags.any(notion_tag)))
            if existing.scalar_one_or_none():
                continue

            tags = _extract_tags(properties) + [notion_tag]
            # Try to get content from rich_text properties
            content = ""
            for key in properties:
                text = _extract_rich_text(properties, key)
                if text and key.lower() not in ("name", "title"):
                    content += text + "\n"

            note = Note(
                title=title,
                content=content.strip() or f"Imported from Notion: {notion_id}",
                source="notion",
                tags=tags,
                project_id=project_id,
            )
            db.add(note)
            created += 1

    db.add(EventLog(
        event_type="notion.imported",
        entity_type="integration",
        source="notion",
        data={"database_id": data.database_id, "import_as": data.import_as, "created": created},
    ))
    await db.flush()

    logger.info(f"Notion import complete: {created} {data.import_as} created")
    return {"imported": True, "created": created, "type": data.import_as}


# ─── Export ───

@router.post("/export")
async def export_to_notion(data: NotionExport, db: AsyncSession = Depends(get_db)):
    """Export MC tasks or notes to a Notion database."""
    import httpx

    _require_notion()
    headers = _notion_headers(settings.notion_api_key)

    exported = 0

    if data.export_type == "tasks":
        query = select(Task)
        if data.project_id:
            query = query.where(Task.project_id == UUID(data.project_id))
        result = await db.execute(query.order_by(Task.created_at.desc()).limit(100))
        items = result.scalars().all()

        for task in items:
            # Skip if already exported (has notion tag)
            if task.tags and any(t.startswith("notion:") for t in task.tags):
                continue

            page_data = {
                "parent": {"database_id": data.database_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": task.text[:2000]}}]},
                },
            }

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{NOTION_API_BASE}/pages",
                        json=page_data,
                        headers=headers,
                    )
                if resp.status_code == 200:
                    notion_id = resp.json().get("id", "")
                    task.tags = list(set((task.tags or []) + [f"notion:{notion_id}"]))
                    exported += 1
            except Exception as e:
                logger.error(f"Notion export failed for task {task.id}: {e}")

    elif data.export_type == "notes":
        query = select(Note)
        if data.project_id:
            query = query.where(Note.project_id == UUID(data.project_id))
        result = await db.execute(query.order_by(Note.created_at.desc()).limit(100))
        items = result.scalars().all()

        for note in items:
            if note.tags and any(t.startswith("notion:") for t in note.tags):
                continue

            page_data = {
                "parent": {"database_id": data.database_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": note.title[:2000]}}]},
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": (note.content or "")[:2000]}}]
                        },
                    }
                ],
            }

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{NOTION_API_BASE}/pages",
                        json=page_data,
                        headers=headers,
                    )
                if resp.status_code == 200:
                    notion_id = resp.json().get("id", "")
                    note.tags = list(set((note.tags or []) + [f"notion:{notion_id}"]))
                    exported += 1
            except Exception as e:
                logger.error(f"Notion export failed for note {note.id}: {e}")

    db.add(EventLog(
        event_type="notion.exported",
        entity_type="integration",
        source="notion",
        data={"database_id": data.database_id, "export_type": data.export_type, "exported": exported},
    ))
    await db.flush()

    logger.info(f"Notion export complete: {exported} {data.export_type} exported")
    return {"exported": True, "count": exported, "type": data.export_type}
