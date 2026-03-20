"""
Telegram Bot Integration

Thin adapter over the shared command layer. All business logic
lives in commands.py — this file only handles Telegram-specific
message formatting and bot lifecycle.
"""

import logging
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters,
)

from app.config import settings
from app.integrations.commands import (
    cmd_task, cmd_idea, cmd_read, cmd_note, cmd_status, cmd_run,
    cmd_projects, cmd_habit, cmd_goal, cmd_journal, cmd_approve, cmd_help,
    cmd_brand, cmd_signals, cmd_agents_list,
)
from app.db.session import async_session
from app.integrations.chat import handle_chat
from app.integrations.voice import transcribe_voice

logger = logging.getLogger(__name__)

SOURCE = "telegram"

# Telegram markdown formatting for section headers
_TG_STATUS_ICONS = {
    "Status": "📊",
    "Projects": "📋",
    "Habits": "↻",
    "Goals": "◎",
    "Journal": "✎",
    "Pending Approvals": "⏳",
    "Commands": "🎯",
}


def _format_reply(text: str) -> tuple[str, str | None]:
    """Add Telegram-specific emoji/markdown formatting to plain command output."""
    # Add icons for section headers (match partial — "MC Status" matches "Status")
    first_line = text.split("\n")[0]
    for keyword, icon in _TG_STATUS_ICONS.items():
        if keyword in first_line:
            text = text.replace(first_line, f"{icon} *{first_line}*", 1)
            return text, "Markdown"

    # Action confirmations
    if text.startswith("Task added:"):
        return f"✅ {text}", None
    if text.startswith("Idea captured:"):
        return f"💡 {text}", None
    if text.startswith("Added to reading list:"):
        return f"📖 {text}", None
    if text.startswith("Note created:"):
        return f"📝 {text}", None
    if text.startswith("Journal entry saved"):
        return f"✎ {text}", None
    if text.startswith("Goal created:"):
        return f"◎ {text}", None
    if text.endswith("completed!"):
        return f"🎉 {text}", None
    if "Streak:" in text:
        return f"✅ {text}", None

    return text, None


def is_allowed(user_id: int) -> bool:
    allowed = settings.telegram_allowed_user_ids
    return not allowed or user_id in allowed


def _make_handler(cmd_fn, needs_args=True):
    """Create a Telegram command handler from a shared command function."""
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_allowed(update.effective_user.id):
            return
        args = " ".join(context.args) if context.args else ""

        if needs_args:
            result = await cmd_fn(args, SOURCE)
        else:
            result = await cmd_fn(SOURCE)

        text, parse_mode = _format_reply(result.text)
        await update.message.reply_text(text, parse_mode=parse_mode)

    return handler


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages via the LLM chat assistant."""
    if not is_allowed(update.effective_user.id):
        return
    text = update.message.text.strip()
    if not text:
        return

    # Check if this is a reply to a signal notification → create draft
    if update.message.reply_to_message and update.message.reply_to_message.text:
        replied_text = update.message.reply_to_message.text
        user_reply = update.message.text

        from app.db.models import MarketingSignal, MarketingContent
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import select

        async with async_session() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            result = await db.execute(
                select(MarketingSignal)
                .where(MarketingSignal.created_at >= cutoff)
                .order_by(MarketingSignal.created_at.desc())
            )
            signals = result.scalars().all()

            matched_signal = None
            for sig in signals:
                if sig.title and sig.title in replied_text:
                    matched_signal = sig
                    break

            if matched_signal:
                channel_map = {"reddit": "reddit_comment", "twitter": "twitter_tweet"}
                channel = channel_map.get(matched_signal.source_type, "other")

                content = MarketingContent(
                    title=f"Re: {matched_signal.title}"[:500],
                    body=user_reply,
                    channel=channel,
                    status="draft",
                    source="telegram",
                    signal_id=matched_signal.id,
                    project_id=matched_signal.project_id,
                )
                db.add(content)
                await db.commit()

                await update.message.reply_text(f"Draft created: Re: {matched_signal.title[:60]}")
                return

    await update.message.chat.send_action("typing")

    try:
        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)
        for reply in replies:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Chat handler error: {e}", exc_info=True)
        await update.message.reply_text(
            f"Sorry, I couldn't process that. Try a /command instead.\n"
            f"Error: {str(e)[:100]}"
        )


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages by transcribing and passing to the chat handler."""
    if not is_allowed(update.effective_user.id):
        return

    await update.message.chat.send_action("typing")

    try:
        # Download the voice file
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        # Transcribe
        text = await transcribe_voice(bytes(audio_bytes), filename="voice.ogg")
        if not text:
            await update.message.reply_text("Could not transcribe the voice message. Please try again.")
            return

        # Show what was heard
        await update.message.reply_text(f"Heard: {text}")

        # Pass transcribed text through the chat handler
        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)
        for reply in replies:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Voice handler error: {e}", exc_info=True)
        await update.message.reply_text(
            f"Sorry, I couldn't process that voice message.\n"
            f"Error: {str(e)[:100]}"
        )


async def start_telegram_bot():
    """Start the Telegram bot."""
    if not settings.telegram_bot_token:
        logger.info("Telegram bot not configured, skipping")
        return

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Register commands using shared handlers
    app.add_handler(CommandHandler("task", _make_handler(cmd_task)))
    app.add_handler(CommandHandler("idea", _make_handler(cmd_idea)))
    app.add_handler(CommandHandler("read", _make_handler(cmd_read)))
    app.add_handler(CommandHandler("note", _make_handler(cmd_note)))
    app.add_handler(CommandHandler("habit", _make_handler(cmd_habit)))
    app.add_handler(CommandHandler("goal", _make_handler(cmd_goal)))
    app.add_handler(CommandHandler("journal", _make_handler(cmd_journal)))
    app.add_handler(CommandHandler("approve", _make_handler(cmd_approve)))
    app.add_handler(CommandHandler("status", _make_handler(cmd_status, needs_args=False)))
    app.add_handler(CommandHandler("run", _make_handler(cmd_run)))
    app.add_handler(CommandHandler("projects", _make_handler(cmd_projects, needs_args=False)))
    app.add_handler(CommandHandler("brand", _make_handler(cmd_brand, needs_args=False)))
    app.add_handler(CommandHandler("signals", _make_handler(cmd_signals)))
    app.add_handler(CommandHandler("agents", _make_handler(cmd_agents_list, needs_args=False)))
    app.add_handler(CommandHandler("help", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(CommandHandler("start", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Set bot commands menu
    await app.bot.set_my_commands([
        BotCommand("task", "Add a task"),
        BotCommand("idea", "Capture an idea"),
        BotCommand("read", "Add to reading list"),
        BotCommand("note", "Create a note"),
        BotCommand("habit", "Complete or create a habit"),
        BotCommand("goal", "View or create goals"),
        BotCommand("journal", "Write a journal entry"),
        BotCommand("approve", "Review pending agent actions"),
        BotCommand("status", "Dashboard stats"),
        BotCommand("run", "Trigger an agent"),
        BotCommand("projects", "List projects"),
        BotCommand("brand", "View brand profile"),
        BotCommand("signals", "View marketing signals"),
        BotCommand("agents", "View agent status"),
        BotCommand("help", "Show commands"),
    ])

    logger.info("Telegram bot started")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        while True:
            await __import__("asyncio").sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
