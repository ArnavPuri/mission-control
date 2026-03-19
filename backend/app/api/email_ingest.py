"""
Email Ingestion - Inbound Webhook API

Accepts POST requests from email forwarding services (SendGrid Inbound Parse,
Mailgun Routes, etc.) and creates Tasks, Ideas, or Notes based on subject
line prefixes.

Mounted at /api/email/inbound
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.models import Task, Idea, Note, EventLog
from app.integrations.email_ingest import parse_subject_prefix

logger = logging.getLogger(__name__)

router = APIRouter()

SOURCE = "email-webhook"


class InboundEmail(BaseModel):
    """Payload from an email forwarding service."""
    from_: str | None = None  # sender address
    subject: str = ""
    body_plain: str = ""
    body_html: str = ""

    model_config = {"populate_by_name": True}

    def __init__(self, **data):
        # Accept "from" key in JSON (reserved word in Python)
        if "from" in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)


@router.post("/inbound")
async def inbound_email(payload: InboundEmail, request: Request, db: AsyncSession = Depends(get_db)):
    """Process an inbound email webhook and create the appropriate entity.

    Accepts JSON with fields: from, subject, body_plain, body_html.
    Parses subject for type prefixes (task:/t:, idea:/i:, note:/n:).
    Requires EMAIL_WEBHOOK_SECRET to be set; pass it as ?secret= query param.
    Returns the created entity ID and type.
    """
    if settings.email_webhook_secret:
        provided = request.query_params.get("secret", "")
        if provided != settings.email_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    entity_type, cleaned_subject = parse_subject_prefix(payload.subject)
    body = payload.body_plain or payload.body_html or ""
    sender = payload.from_ or "unknown"

    if entity_type == "task":
        obj = Task(text=cleaned_subject, source=SOURCE)
        db.add(obj)
        await db.flush()
        entity_id = str(obj.id)

        event = EventLog(
            event_type="task.created",
            entity_type="task",
            entity_id=obj.id,
            source=SOURCE,
            data={"text": cleaned_subject, "sender": sender},
        )
        db.add(event)

    elif entity_type == "idea":
        obj = Idea(text=cleaned_subject, source=SOURCE)
        db.add(obj)
        await db.flush()
        entity_id = str(obj.id)

        event = EventLog(
            event_type="idea.created",
            entity_type="idea",
            entity_id=obj.id,
            source=SOURCE,
            data={"text": cleaned_subject, "sender": sender},
        )
        db.add(event)

    elif entity_type == "note":
        obj = Note(title=cleaned_subject, content=body, source=SOURCE)
        db.add(obj)
        await db.flush()
        entity_id = str(obj.id)

        event = EventLog(
            event_type="note.created",
            entity_type="note",
            entity_id=obj.id,
            source=SOURCE,
            data={"title": cleaned_subject, "sender": sender},
        )
        db.add(event)

    else:
        # Should not happen, but fall back to task
        obj = Task(text=cleaned_subject, source=SOURCE)
        db.add(obj)
        await db.flush()
        entity_id = str(obj.id)

    logger.info(f"Email webhook: created {entity_type} '{cleaned_subject}' (id={entity_id}) from {sender}")

    return {
        "id": entity_id,
        "entity_type": entity_type,
        "title": cleaned_subject,
        "source": SOURCE,
    }
