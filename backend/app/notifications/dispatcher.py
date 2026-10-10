"""Telegram notification dispatcher — sends urgent notifications immediately; routine activity goes into the morning briefing."""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select, update

from app.config import settings
from app.db.session import async_session
from app.db.models import Notification, NotificationPriority

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(text: str, reply_markup: dict | None = None) -> int | None:
    """Send a message via the Telegram Bot API. Returns the message id, or None on failure.

    Agent output often contains characters that break Telegram's Markdown
    parser (underscores in URLs, unbalanced asterisks). If Telegram rejects
    the formatting, the message is resent as plain text instead of failing.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_target_chat_id
    if not token or not chat_id:
        logger.warning("Telegram not configured for notifications (missing token or chat_id)")
        return None

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 400 and "parse entities" in resp.text:
                payload.pop("parse_mode")
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"Telegram send failed ({resp.status_code}): {resp.text}")
                return None
            return resp.json().get("result", {}).get("message_id")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return None


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

            if await send_telegram(text):
                notif.telegram_sent = True

        await db.commit()


async def mark_routine_sent():
    """Mark routine notifications as delivered.

    Routine notifications are not sent one by one: the morning briefing
    summarises the same activity from live data, so after it goes out the
    pending routine notifications are considered delivered.
    """
    async with async_session() as db:
        await db.execute(
            update(Notification)
            .where(
                Notification.priority == NotificationPriority.ROUTINE,
                Notification.telegram_sent == False,
            )
            .values(telegram_sent=True)
        )
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
    """Daily loop — sends the morning briefing at 8:00 AM in the configured timezone."""
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

            from app.notifications.morning import send_morning_briefing
            if await send_morning_briefing():
                await mark_routine_sent()
        except Exception as e:
            logger.error(f"Digest loop error: {e}")
            await asyncio.sleep(3600)
