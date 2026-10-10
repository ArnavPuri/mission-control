"""
Telegram Bot — Primary interface to Mission Control.

Supports slash commands, natural language chat, and voice messages.
"""

import logging
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

from app.config import settings
from app.integrations.commands import (
    cmd_task, cmd_note, cmd_status, cmd_run, cmd_ask,
    cmd_projects, cmd_approve, cmd_help,
    cmd_brand, cmd_leads, cmd_agents_list, cmd_morning, cmd_drafts, cmd_dev, cmd_repo,
)
from app.db.session import async_session
from app.integrations.chat import handle_chat
from app.integrations import github
from app.orchestrator import review, threads

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
        await reply(update.message, text, parse_mode=result.parse_mode or parse_mode,
                    reply_markup=_markup(result.reply_markup))
        for followup in result.followups:
            await reply(update.message, followup.text, parse_mode=followup.parse_mode,
                        reply_markup=_markup(followup.reply_markup))

    return handler


def _markup(data: dict | None) -> InlineKeyboardMarkup | None:
    if not data:
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row]
        for row in data["inline_keyboard"]
    ])


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button presses: approve/reject actions, approve/post/discard drafts."""
    query = update.callback_query
    if not is_allowed(query.from_user.id):
        await query.answer("Not authorized", show_alert=True)
        return
    async with async_session() as db:
        outcome = await review.handle_callback(db, query.data or "")
        await db.commit()
    await query.answer(outcome[:200])
    # Keep the message, drop the buttons, and show what happened
    original = query.message.text if query.message else ""
    try:
        await query.edit_message_text(f"{original}\n\n→ {outcome}")
    except BadRequest:
        await query.edit_message_reply_markup(None)


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages via the LLM chat assistant."""
    if not await check_allowed(update):
        return
    text = update.message.text.strip()
    if not text:
        return

    # A reply to an agent's message continues that task's thread
    replied_to = update.message.reply_to_message
    if replied_to:
        async with async_session() as db:
            task = await threads.find_task_by_telegram_message(db, replied_to.message_id)
            if task:
                agent = await threads.add_user_reply(db, task, text, telegram_message_id=update.message.message_id)
                if agent:
                    note = f"↩️ Sent to {agent.name}"
                elif github.issue_ref(task):
                    note = "↩️ Posted on the GitHub issue"
                else:
                    note = "📝 Added to the task thread"
                await reply(update.message, note)
                return

    await update.message.chat.send_action("typing")

    try:
        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)
        for chunk in replies:
            await update.message.reply_text(chunk)
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
        for chunk in replies:
            await update.message.reply_text(chunk)

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
    app.add_handler(CommandHandler("drafts", _make_handler(cmd_drafts, needs_args=False)))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(CommandHandler("status", _make_handler(cmd_status, needs_args=False)))
    app.add_handler(CommandHandler("ask", _make_handler(cmd_ask)))
    app.add_handler(CommandHandler("dev", _make_handler(cmd_dev)))
    app.add_handler(CommandHandler("repo", _make_handler(cmd_repo)))
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
        BotCommand("drafts", "Review content drafts"),
        BotCommand("status", "Dashboard stats"),
        BotCommand("ask", "Hand a task to an agent"),
        BotCommand("dev", "Hand coding work to Claude Code"),
        BotCommand("repo", "Link a project to its GitHub repo"),
        BotCommand("run", "Run an agent's scheduled job now"),
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
