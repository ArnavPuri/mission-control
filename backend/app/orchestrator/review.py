"""
Reviewing agent output: approvals and content drafts.

Shared by the API, Telegram commands and Telegram's inline buttons, so an
approval or draft is handled the same way wherever you tap.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import publishing
from app.orchestrator import reminders
from app.db.models import (
    AgentApproval, AgentConfig, ApprovalStatus, ContentStatus, EventLog, MarketingContent,
)

logger = logging.getLogger(__name__)

# Telegram callback_data prefixes (callback_data is limited to 64 bytes)
APPROVAL_CB = "apr"
CONTENT_CB = "cnt"

# Content button verbs besides the statuses
PUBLISH, PUBLISH_NOW, CANCEL = "publish", "publishnow", "cancel"
CHANNEL_NAMES = {"x": "X", "linkedin": "LinkedIn"}


@dataclass
class Confirm:
    """A button press that asks a follow-up: show text and swap the buttons."""
    text: str
    markup: dict


CONTENT_LABELS = {
    ContentStatus.APPROVED: "✅ Approved",
    ContentStatus.POSTED: "📤 Marked as posted",
    ContentStatus.ARCHIVED: "🗑 Discarded",
}


def _keyboard(*rows: list[tuple[str, str]]) -> dict:
    """Telegram Bot API inline_keyboard markup."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def _describe_action(action: dict) -> str:
    kind = action.get("type", "?")
    what = action.get("text") or action.get("title") or action.get("key") or ""
    if kind == "update_task":
        changes = ", ".join(f"{k}→{action[k]}" for k in ("status", "priority") if action.get(k))
        what = f"{action.get('task_id', '')[:8]} {changes}"
    elif kind == "handoff":
        what = f"to {action.get('agent', '?')}: {(action.get('request') or '')[:120]}"
    return f"• {kind}: {what}"[:200]


def approval_message(approval: AgentApproval, agent_name: str) -> tuple[str, dict]:
    actions = approval.actions if isinstance(approval.actions, list) else []
    lines = [f"⏳ *{agent_name}* wants to take {len(actions)} action{'s' if len(actions) != 1 else ''}"]
    if approval.summary:
        lines.append(approval.summary[:500])
    lines.append("")
    lines.extend(_describe_action(a) for a in actions[:10])
    if len(actions) > 10:
        lines.append(f"…and {len(actions) - 10} more")
    markup = _keyboard([
        ("✅ Approve", f"{APPROVAL_CB}:y:{approval.id}"),
        ("❌ Reject", f"{APPROVAL_CB}:n:{approval.id}"),
    ])
    return "\n".join(lines), markup


def draft_message(content: MarketingContent) -> tuple[str, dict]:
    body = content.body if len(content.body) <= 3000 else content.body[:3000] + "…"
    text = f"📝 *{content.channel}* · {content.title}\n\n{body}"
    return text, _draft_keyboard(content)


def _draft_keyboard(content: MarketingContent) -> dict:
    rows = [[
        ("✅ Approve", f"{CONTENT_CB}:approved:{content.id}"),
        ("📤 Posted", f"{CONTENT_CB}:posted:{content.id}"),
        ("🗑 Discard", f"{CONTENT_CB}:archived:{content.id}"),
    ]]
    if publishing.can_publish(content.channel):
        rows.append([(f"🚀 Publish to {CHANNEL_NAMES[content.channel]}", f"{CONTENT_CB}:{PUBLISH}:{content.id}")])
    return _keyboard(*rows)


async def publish_content(db: AsyncSession, content_id: UUID, source: str = "user") -> tuple[bool, str]:
    """Publish a draft to its channel. Returns (published, message); the message
    has the post's URL or why it couldn't be published."""
    content = await db.get(MarketingContent, content_id)
    if not content:
        return False, "That draft no longer exists."
    if content.status == ContentStatus.POSTED:
        return False, f"Already posted{': ' + content.posted_url if content.posted_url else '.'}"
    try:
        url = await publishing.publish(content.channel, content.body)
    except publishing.PublishError as e:
        logger.warning(f"Publishing {content.id} to {content.channel} failed: {e}")
        return False, f"⚠️ Couldn't publish: {e}"
    content.status = ContentStatus.POSTED
    content.posted_at = datetime.now(timezone.utc)
    content.posted_url = url
    db.add(EventLog(
        event_type="content.published", entity_type="content", entity_id=content.id,
        source=source, data={"channel": content.channel, "url": url},
    ))
    await db.flush()
    return True, f"🚀 Published: {url}"


async def pending_approvals(db: AsyncSession) -> list[AgentApproval]:
    """Pending approvals, expiring the ones past their deadline."""
    result = await db.execute(
        select(AgentApproval)
        .where(AgentApproval.status == ApprovalStatus.PENDING)
        .order_by(AgentApproval.created_at.desc())
    )
    now = datetime.now(timezone.utc)
    pending = []
    for a in result.scalars().all():
        expires = a.expires_at.replace(tzinfo=a.expires_at.tzinfo or timezone.utc) if a.expires_at else None
        if expires and expires < now:
            a.status = ApprovalStatus.EXPIRED
        else:
            pending.append(a)
    await db.flush()
    return pending


async def resolve_approval(db: AsyncSession, approval_id: UUID, approve: bool) -> str:
    """Approve (and apply) or reject an approval. Returns a short outcome message."""
    from app.orchestrator.runner import AgentRunner

    approval = await db.get(AgentApproval, approval_id)
    if not approval:
        return "That approval no longer exists."
    if approval.status != ApprovalStatus.PENDING:
        return f"Already {approval.status.value}."
    approval.reviewed_at = datetime.now(timezone.utc)
    if not approve:
        approval.status = ApprovalStatus.REJECTED
        await db.flush()
        return "❌ Rejected"

    approval.status = ApprovalStatus.APPROVED
    agent = await db.get(AgentConfig, approval.agent_id)
    warnings = await AgentRunner().process_actions(approval.actions, agent, db) if agent else []
    await db.flush()
    applied = len(approval.actions) - len(warnings)
    note = f" ({len(warnings)} skipped)" if warnings else ""
    return f"✅ Approved — {applied} action{'s' if applied != 1 else ''} applied{note}"


async def pending_drafts(db: AsyncSession, limit: int = 5) -> list[MarketingContent]:
    result = await db.execute(
        select(MarketingContent)
        .where(MarketingContent.status == ContentStatus.DRAFT)
        .order_by(MarketingContent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def set_content_status(db: AsyncSession, content_id: UUID, status: ContentStatus) -> str:
    content = await db.get(MarketingContent, content_id)
    if not content:
        return "That draft no longer exists."
    content.status = status
    if status == ContentStatus.POSTED and not content.posted_at:
        content.posted_at = datetime.now(timezone.utc)
    await db.flush()
    return CONTENT_LABELS.get(status, status.value)


async def handle_callback(db: AsyncSession, data: str) -> str | Confirm:
    """Apply an inline-button press. Returns the outcome to show on the message,
    or a Confirm when the press needs a second tap."""
    try:
        kind, verb, raw_id = data.split(":", 2)
        item_id = UUID(raw_id)
    except ValueError:
        return "Unknown button."
    if kind == reminders.REMINDER_CB:
        return await reminders.handle_callback(db, verb, item_id)
    if kind == APPROVAL_CB and verb in ("y", "n"):
        return await resolve_approval(db, item_id, approve=verb == "y")
    if kind == CONTENT_CB and verb in (PUBLISH, PUBLISH_NOW, CANCEL):
        content = await db.get(MarketingContent, item_id)
        if not content:
            return "That draft no longer exists."
        if verb == PUBLISH:
            # Posting publicly is one tap too easy to hit by accident: ask once more
            where = CHANNEL_NAMES.get(content.channel, content.channel)
            return Confirm(f"Publish this to {where} now?", _keyboard([
                (f"🚀 Yes, publish to {where}", f"{CONTENT_CB}:{PUBLISH_NOW}:{content.id}"),
                ("Cancel", f"{CONTENT_CB}:{CANCEL}:{content.id}"),
            ]))
        if verb == CANCEL:
            return Confirm("Not published", _draft_keyboard(content))
        return (await publish_content(db, item_id, source="telegram"))[1]
    if kind == CONTENT_CB:
        try:
            status = ContentStatus(verb)
        except ValueError:
            return "Unknown button."
        return await set_content_status(db, item_id, status)
    return "Unknown button."
