"""Approvals and content drafts handled from Telegram buttons."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    AgentApproval, AgentConfig, ApprovalStatus, ContentStatus,
    MarketingContent, Task,
)
from app.integrations import commands
from app.notifications import dispatcher
from app.orchestrator import review
from app.orchestrator.runner import AgentRunner


async def gated_run(db_session, monkeypatch) -> AgentApproval:
    async def fake(self, prompt, agent):
        return {"summary": "Two follow-ups", "actions": [
            {"type": "create_task", "text": "Email Sam"},
            {"type": "create_task", "text": "Call Alex"},
        ]}
    monkeypatch.setattr(AgentRunner, "execute_with_agent_sdk", fake)
    agent = AgentConfig(name="Careful", slug="careful", agent_type="ops", prompt_template="p",
                        data_writes=["tasks"], config={"requires_approval": True})
    async with db_session() as db:
        db.add(agent)
        await db.commit()
        await AgentRunner().start_run(agent, trigger="manual", db=db)
        return (await db.execute(select(AgentApproval))).scalar_one()


@pytest.mark.asyncio
async def test_approval_notification_carries_buttons_and_is_sent_with_them(db_session, monkeypatch):
    approval = await gated_run(db_session, monkeypatch)
    sent = []

    async def fake_send(text, reply_markup=None):
        sent.append((text, reply_markup))
        return 1

    monkeypatch.setattr(dispatcher, "send_telegram", fake_send)
    await dispatcher.dispatch_urgent()

    text, markup = next(m for m in sent if m[1])
    assert "Email Sam" in text and "Call Alex" in text
    buttons = [b["callback_data"] for b in markup["inline_keyboard"][0]]
    assert buttons == [f"apr:y:{approval.id}", f"apr:n:{approval.id}"]


@pytest.mark.asyncio
async def test_approve_button_applies_actions_once(db_session, monkeypatch):
    approval = await gated_run(db_session, monkeypatch)

    async with db_session() as db:
        outcome = await review.handle_callback(db, f"apr:y:{approval.id}")
        await db.commit()
    assert outcome == "✅ Approved — 2 actions applied"

    async with db_session() as db:
        again = await review.handle_callback(db, f"apr:y:{approval.id}")
        texts = sorted(t.text for t in (await db.execute(select(Task))).scalars().all())
    assert again == "Already approved."
    assert texts == ["Call Alex", "Email Sam"]


@pytest.mark.asyncio
async def test_reject_button(db_session, monkeypatch):
    approval = await gated_run(db_session, monkeypatch)
    async with db_session() as db:
        assert await review.handle_callback(db, f"apr:n:{approval.id}") == "❌ Rejected"
        await db.commit()
        assert (await db.get(AgentApproval, approval.id)).status == ApprovalStatus.REJECTED
        assert (await db.execute(select(Task))).scalars().all() == []


@pytest.mark.asyncio
async def test_expired_approvals_are_not_offered(db_session, monkeypatch):
    approval = await gated_run(db_session, monkeypatch)
    async with db_session() as db:
        a = await db.get(AgentApproval, approval.id)
        a.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()

    result = await commands.cmd_approve("", "telegram")
    assert result.text == "No pending approvals."
    async with db_session() as db:
        assert (await db.get(AgentApproval, approval.id)).status == ApprovalStatus.EXPIRED


@pytest.mark.asyncio
async def test_approve_command_sends_one_message_per_approval(db_session, monkeypatch):
    approval = await gated_run(db_session, monkeypatch)
    result = await commands.cmd_approve("", "telegram")
    assert result.text == "1 pending approval:"
    assert result.followups[0].reply_markup["inline_keyboard"][0][0]["callback_data"] == f"apr:y:{approval.id}"


@pytest.mark.asyncio
async def test_draft_buttons(db_session):
    draft = MarketingContent(title="Launch tweet", body="We shipped!", channel="x")
    async with db_session() as db:
        db.add(draft)
        await db.commit()

    result = await commands.cmd_drafts("telegram")
    callbacks = [b["callback_data"] for b in result.followups[0].reply_markup["inline_keyboard"][0]]
    assert callbacks == [f"cnt:approved:{draft.id}", f"cnt:posted:{draft.id}", f"cnt:archived:{draft.id}"]

    async with db_session() as db:
        assert await review.handle_callback(db, f"cnt:posted:{draft.id}") == "📤 Marked as posted"
        await db.commit()
        posted = await db.get(MarketingContent, draft.id)
    assert posted.status == ContentStatus.POSTED and posted.posted_at is not None
    assert (await commands.cmd_drafts("telegram")).text == "No content drafts waiting."


@pytest.mark.asyncio
async def test_unknown_button(db_session):
    async with db_session() as db:
        assert await review.handle_callback(db, "zzz") == "Unknown button."
        assert await review.handle_callback(db, "cnt:bogus:00000000-0000-0000-0000-000000000000") == "Unknown button."


@pytest.mark.asyncio
async def test_telegram_button_handler(db_session, monkeypatch):
    """The python-telegram-bot handler: answers the press and edits the message."""
    from types import SimpleNamespace
    from app.config import settings
    from app.integrations import telegram as tg

    monkeypatch.setattr(settings, "telegram_allowed_users", "42")
    draft = MarketingContent(title="Post", body="Body", channel="linkedin")
    async with db_session() as db:
        db.add(draft)
        await db.commit()

    calls = {}

    async def answer(text=None, show_alert=False):
        calls["answer"] = text

    async def edit_message_text(text):
        calls["edited"] = text

    query = SimpleNamespace(
        from_user=SimpleNamespace(id=42), data=f"cnt:approved:{draft.id}",
        message=SimpleNamespace(text="📝 linkedin · Post"), answer=answer,
        edit_message_text=edit_message_text,
    )
    await tg.handle_button(SimpleNamespace(callback_query=query), None)

    assert calls == {"answer": "✅ Approved", "edited": "📝 linkedin · Post\n\n→ ✅ Approved"}
    async with db_session() as db:
        assert (await db.get(MarketingContent, draft.id)).status == ContentStatus.APPROVED

    # Strangers get nothing done
    query.from_user = SimpleNamespace(id=7)
    calls.clear()
    await tg.handle_button(SimpleNamespace(callback_query=query), None)
    assert calls == {"answer": "Not authorized"}


def test_markup_builds_telegram_keyboard():
    from app.integrations.telegram import _markup
    markup = _markup({"inline_keyboard": [[{"text": "OK", "callback_data": "apr:y:1"}]]})
    assert markup.inline_keyboard[0][0].callback_data == "apr:y:1"
    assert _markup(None) is None
