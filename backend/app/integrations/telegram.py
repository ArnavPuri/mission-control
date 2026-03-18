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
)
from app.db.session import async_session
from app.integrations.chat import handle_chat

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
    app.add_handler(CommandHandler("help", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(CommandHandler("start", _make_handler(cmd_help, needs_args=False)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))

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
