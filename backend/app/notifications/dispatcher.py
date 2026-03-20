"""Telegram notification dispatcher — sends urgent notifications immediately, routine ones as a morning digest."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select

from app.config import settings
from app.db.session import async_session
from app.db.models import Notification, NotificationPriority

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def _send_telegram(text: str) -> bool:
    """Send a message via Telegram Bot API using httpx. Returns True on success."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_target_chat_id
    if not token or not chat_id:
        logger.warning("Telegram not configured for notifications (missing token or chat_id)")
        return False

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
            if resp.status_code != 200:
                logger.error(f"Telegram send failed ({resp.status_code}): {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def dispatch_urgent():
    """Send all unsent urgent notifications to Telegram."""
    async with async_session() as db:
        result = await db.execute(
            select(Notification).where(
                Notification.priority == NotificationPriority.URGENT,
                Notification.telegram_sent == False,
            ).order_by(Notification.created_at.asc())
        )
        notifications = result.scalars().all()

        for notif in notifications:
            text = f"*{notif.title}*\n{notif.body}" if notif.body else f"*{notif.title}*"
            if notif.action_url:
                text += f"\n{notif.action_url}"

            sent = await _send_telegram(text)
            if sent:
                notif.telegram_sent = True

        await db.commit()


async def dispatch_digest():
    """Send daily digest of unsent routine notifications."""
    async with async_session() as db:
        result = await db.execute(
            select(Notification).where(
                Notification.priority == NotificationPriority.ROUTINE,
                Notification.telegram_sent == False,
            ).order_by(Notification.created_at.asc())
        )
        notifications = result.scalars().all()

        if not notifications:
            return

        lines = ["*Morning Briefing*", ""]

        agent_notifs = [n for n in notifications if n.source.startswith("agent:")]
        completed = sum(1 for n in agent_notifs if n.category == "success")
        failed = sum(1 for n in agent_notifs if n.category == "error")
        if agent_notifs:
            lines.append(f"Agents: {completed} completed, {failed} failed")

        signal_notifs = [n for n in notifications if "signal" in (n.category or "")]
        if signal_notifs:
            lines.append(f"Signals: {len(signal_notifs)} new")

        content_notifs = [n for n in notifications if "content" in (n.category or "")]
        if content_notifs:
            lines.append(f"Content: {len(content_notifs)} drafts ready")

        task_notifs = [n for n in notifications if "task" in (n.source or "")]
        if task_notifs:
            lines.append(f"Tasks: {len(task_notifs)} created by agents")

        top_signal = None
        for n in signal_notifs:
            score = (n.data or {}).get("relevance_score", 0)
            if top_signal is None or score > (top_signal.data or {}).get("relevance_score", 0):
                top_signal = n
        if top_signal:
            score_pct = int((top_signal.data or {}).get("relevance_score", 0) * 100)
            lines.append(f"\nTop signal: {top_signal.title} ({score_pct}%)")

        approval_count = sum(1 for n in notifications if n.category == "approval")
        if approval_count:
            lines.append(f"\n{approval_count} pending approvals — use /approve")

        text = "\n".join(lines)
        sent = await _send_telegram(text)

        if sent:
            for n in notifications:
                n.telegram_sent = True
            await db.commit()


async def urgent_dispatch_loop():
    """Polling loop for urgent notifications — runs every 30 seconds."""
    logger.info("Telegram urgent dispatcher started (30s interval)")
    while True:
        try:
            await dispatch_urgent()
        except Exception as e:
            logger.error(f"Urgent dispatch error: {e}")
        await asyncio.sleep(30)


async def digest_loop():
    """Daily digest loop — sends at 8:00 AM in configured timezone."""
    import zoneinfo
    logger.info(f"Telegram digest loop started (8:00 AM {settings.notification_timezone})")

    while True:
        try:
            tz = zoneinfo.ZoneInfo(settings.notification_timezone)
            now = datetime.now(tz)
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            await dispatch_digest()
        except Exception as e:
            logger.error(f"Digest loop error: {e}")
            await asyncio.sleep(3600)
