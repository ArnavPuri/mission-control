"""
Telegram Bot — Primary interface to Mission Control.

Supports slash commands, natural language chat, and voice messages.
"""

import logging
from telegram import Update, BotCommand
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters,
)

from app.config import settings
from app.integrations.commands import (
    cmd_task, cmd_note, cmd_status, cmd_run,
    cmd_projects, cmd_approve, cmd_help,
    cmd_brand, cmd_leads, cmd_agents_list, cmd_morning,
)
from app.db.session import async_session
from app.integrations.chat import handle_chat

logger = logging.getLogger(__name__)

SOURCE = "telegram"

_TG_STATUS_ICONS = {
    "Status": "📊",
    "Projects": "📋",
    "Pending Approvals": "⏳",
    "Commands": "🎯",
}


def _format_reply(text: str) -> tuple[str, str | None]:
    """Add Telegram-specific formatting."""
    first_line = text.split("\n")[0]
    for keyword, icon in _TG_STATUS_ICONS.items():
        if keyword in first_line:
            text = text.replace(first_line, f"{icon} *{first_line}*", 1)
            return text, "Markdown"

    if text.startswith("Task added:"):
        return f"✅ {text}", None
    if text.startswith("Note created:"):
        return f"📝 {text}", None

    return text, None


def is_allowed(user_id: int) -> bool:
    """Only users listed in TELEGRAM_ALLOWED_USERS may use the bot. With the list
    empty nobody can — the bot can start agents, so it must never be open."""
    return user_id in settings.telegram_allowed_user_ids


async def check_allowed(update: Update) -> bool:
    user = update.effective_user
    if user and is_allowed(user.id):
        return True
    if user and update.effective_message:
        logger.warning(f"Rejected Telegram user {user.id} (@{user.username})")
        await update.effective_message.reply_text(
            f"Not authorized. Your Telegram user ID is {user.id} — add it to "
            "TELEGRAM_ALLOWED_USERS in .env and restart Mission Control."
        )
    return False


async def reply(message, text: str, parse_mode: str | None = None, **kwargs):
    """Reply, falling back to plain text if Telegram can't parse the Markdown."""
    try:
        return await message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except BadRequest as e:
        if parse_mode and "parse entities" in str(e).lower():
            return await message.reply_text(text, **kwargs)
        raise


def _make_handler(cmd_fn, needs_args=True):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_allowed(update):
            return
        args = " ".join(context.args) if context.args else ""

        if needs_args:
            result = await cmd_fn(args, SOURCE)
        else:
            result = await cmd_fn(SOURCE)

        text, parse_mode = _format_reply(result.text)
        await reply(update.message, text, parse_mode=result.parse_mode or parse_mode)

    return handler


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages via the LLM chat assistant."""
    if not await check_allowed(update):
        return
    text = update.message.text.strip()
    if not text:
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
    """Handle voice messages by transcribing and passing to chat."""
    if not await check_allowed(update):
        return

    await update.message.chat.send_action("typing")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        # Try to transcribe with OpenAI Whisper
        import httpx
        if not settings.openai_api_key:
            await update.message.reply_text("Voice transcription requires OPENAI_API_KEY to be set.")
            return

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": ("voice.ogg", bytes(audio_bytes), "audio/ogg")},
                data={"model": "whisper-1"},
            )
            resp.raise_for_status()
            text = resp.json().get("text", "")

        if not text:
            await update.message.reply_text("Could not transcribe the voice message.")
            return

        await update.message.reply_text(f"Heard: {text}")

        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)
        for reply in replies:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Voice handler error: {e}", exc_info=True)
        await update.message.reply_text(f"Sorry, couldn't process that voice message.\nError: {str(e)[:100]}")


async def start_telegram_bot():
    """Start the Telegram bot."""
    if not settings.telegram_bot_token:
        logger.info("Telegram bot not configured, skipping")
        return
    if not settings.telegram_allowed_user_ids:
        logger.warning("TELEGRAM_ALLOWED_USERS is empty — the bot will reject every message until it is set")

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Register commands
    app.add_handler(CommandHandler("task", _make_handler(cmd_task)))
    app.add_handler(CommandHandler("note", _make_handler(cmd_note)))
    app.add_handler(CommandHandler("approve", _make_handler(cmd_approve)))
    app.add_handler(CommandHandler("status", _make_handler(cmd_status, needs_args=False)))
    app.add_handler(CommandHandler("run", _make_handler(cmd_run)))
    app.add_handler(CommandHandler("projects", _make_handler(cmd_projects, needs_args=False)))
    app.add_handler(CommandHandler("brand", _make_handler(cmd_brand, needs_args=False)))
    app.add_handler(CommandHandler("leads", _make_handler(cmd_leads)))
    app.add_handler(CommandHandler("agents", _make_handler(cmd_agents_list, needs_args=False)))
    app.add_handler(CommandHandler("morning", _make_handler(cmd_morning, needs_args=False)))
    app.add_handler(CommandHandler("help", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(CommandHandler("start", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Set bot commands menu
    await app.bot.set_my_commands([
        BotCommand("task", "Add a task"),
        BotCommand("note", "Create a note"),
        BotCommand("approve", "Review pending agent actions"),
        BotCommand("status", "Dashboard stats"),
        BotCommand("run", "Trigger an agent"),
        BotCommand("projects", "List projects"),
        BotCommand("brand", "View brand profile"),
        BotCommand("leads", "View open marketing leads"),
        BotCommand("agents", "View agent status"),
        BotCommand("morning", "Morning briefing"),
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
