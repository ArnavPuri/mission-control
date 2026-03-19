"""Webhook Templates for common services.

Pre-built configurations for popular integrations like Slack, Discord, GitHub, etc.
Users can create webhooks from templates with minimal configuration.
"""

from uuid import uuid4
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import WebhookConfig

router = APIRouter()


# --- Template Definitions ---

WEBHOOK_TEMPLATES = {
    "slack-notifications": {
        "name": "Slack Notifications",
        "description": "Send Mission Control events to a Slack channel via incoming webhook",
        "direction": "outbound",
        "events": ["task.created", "task.completed", "agent.completed", "agent.failed"],
        "headers": {"Content-Type": "application/json"},
        "required_fields": ["url"],
        "example_url": "https://hooks.slack.com/services/T00/B00/xxxx",
        "payload_format": "slack",
        "docs_url": "https://api.slack.com/messaging/webhooks",
    },
    "discord-webhook": {
        "name": "Discord Webhook",
        "description": "Post Mission Control events to a Discord channel",
        "direction": "outbound",
        "events": ["task.created", "task.completed", "agent.completed", "agent.failed"],
        "headers": {"Content-Type": "application/json"},
        "required_fields": ["url"],
        "example_url": "https://discord.com/api/webhooks/1234/abcd",
        "payload_format": "discord",
        "docs_url": "https://discord.com/developers/docs/resources/webhook",
    },
    "github-events": {
        "name": "GitHub Events",
        "description": "Receive GitHub webhook events (push, PR, issues)",
        "direction": "inbound",
        "events": ["push", "pull_request", "issues", "issue_comment"],
        "headers": {},
        "required_fields": [],
        "signature_header": "x-hub-signature-256",
        "payload_format": "github",
        "docs_url": "https://docs.github.com/en/webhooks",
    },
    "stripe-events": {
        "name": "Stripe Events",
        "description": "Receive Stripe payment events (charges, subscriptions, invoices)",
        "direction": "inbound",
        "events": ["charge.succeeded", "charge.failed", "invoice.paid", "customer.subscription.*"],
        "headers": {},
        "required_fields": [],
        "signature_header": "stripe-signature",
        "payload_format": "stripe",
        "docs_url": "https://stripe.com/docs/webhooks",
    },
    "linear-events": {
        "name": "Linear Events",
        "description": "Receive Linear issue and project events",
        "direction": "inbound",
        "events": ["Issue", "Comment", "Project"],
        "headers": {},
        "required_fields": [],
        "payload_format": "linear",
        "docs_url": "https://linear.app/docs/webhooks",
    },
    "email-notification": {
        "name": "Email via Sendgrid",
        "description": "Send email notifications for important events via Sendgrid",
        "direction": "outbound",
        "events": ["agent.failed", "task.overdue"],
        "headers": {"Content-Type": "application/json"},
        "required_fields": ["url", "api_key"],
        "example_url": "https://api.sendgrid.com/v3/mail/send",
        "payload_format": "sendgrid",
        "docs_url": "https://docs.sendgrid.com/api-reference/mail-send/mail-send",
    },
    "generic-outbound": {
        "name": "Generic Outbound",
        "description": "Send JSON payloads to any URL when events occur",
        "direction": "outbound",
        "events": ["*"],
        "headers": {"Content-Type": "application/json"},
        "required_fields": ["url"],
        "payload_format": "standard",
    },
    "generic-inbound": {
        "name": "Generic Inbound",
        "description": "Receive webhooks from any service with HMAC signature verification",
        "direction": "inbound",
        "events": ["*"],
        "headers": {},
        "required_fields": [],
        "payload_format": "standard",
    },
}


class TemplateCreate(BaseModel):
    template_id: str
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None  # override default events
    name: str | None = None  # override default name
    api_key: str | None = None  # for services like Sendgrid


@router.get("/templates")
async def list_templates():
    """List all available webhook templates."""
    return [
        {
            "id": tid,
            "name": t["name"],
            "description": t["description"],
            "direction": t["direction"],
            "default_events": t["events"],
            "required_fields": t["required_fields"],
            "docs_url": t.get("docs_url"),
        }
        for tid, t in WEBHOOK_TEMPLATES.items()
    ]


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get details of a specific webhook template."""
    template = WEBHOOK_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"id": template_id, **template}


@router.post("/templates/create")
async def create_from_template(data: TemplateCreate, db: AsyncSession = Depends(get_db)):
    """Create a webhook from a template.

    Automatically configures events, headers, and generates secrets for inbound hooks.
    """
    template = WEBHOOK_TEMPLATES.get(data.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{data.template_id}' not found")

    # Validate required fields
    if "url" in template["required_fields"] and not data.url:
        raise HTTPException(status_code=400, detail="This template requires a URL")

    # Build headers
    headers = dict(template["headers"])
    if data.api_key:
        headers["Authorization"] = f"Bearer {data.api_key}"

    # Generate secret for inbound webhooks
    secret = data.secret
    if template["direction"] == "inbound" and not secret:
        secret = hashlib.sha256(uuid4().bytes).hexdigest()[:32]

    hook = WebhookConfig(
        name=data.name or template["name"],
        direction=template["direction"],
        url=data.url,
        secret=secret,
        events=data.events or template["events"],
        headers=headers,
    )
    db.add(hook)
    await db.flush()

    result = {
        "id": str(hook.id),
        "name": hook.name,
        "direction": hook.direction,
        "template": data.template_id,
        "events": hook.events,
    }

    if template["direction"] == "inbound":
        result["endpoint"] = f"/api/webhooks/in/{hook.id}"
        result["secret"] = secret
    if template.get("docs_url"):
        result["docs_url"] = template["docs_url"]

    return result
