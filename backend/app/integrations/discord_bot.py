"""
Discord Bot Integration

Thin adapter over the shared command layer. All business logic
lives in commands.py — this file only handles Discord-specific
message routing and bot lifecycle.
"""

import logging

from app.config import settings
from app.integrations.commands import (
    cmd_task, cmd_idea, cmd_read, cmd_note, cmd_status, cmd_run,
    cmd_projects, cmd_habit, cmd_goal, cmd_journal, cmd_approve, cmd_help,
)

logger = logging.getLogger(__name__)

SOURCE = "discord"

# Map !command names to (handler_fn, needs_args)
COMMANDS = {
    "!task": (cmd_task, True),
    "!idea": (cmd_idea, True),
    "!read": (cmd_read, True),
    "!note": (cmd_note, True),
    "!habit": (cmd_habit, True),
    "!goal": (cmd_goal, True),
    "!journal": (cmd_journal, True),
    "!approve": (cmd_approve, True),
    "!status": (cmd_status, False),
    "!run": (cmd_run, True),
    "!projects": (cmd_projects, False),
    "!help": (cmd_help, False),
}


async def start_discord_bot():
    """Start the Discord bot."""
    if not settings.discord_bot_token:
        logger.info("Discord bot not configured, skipping")
        return

    try:
        import discord
    except ImportError:
        logger.warning("discord.py not installed — pip install discord.py")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    allowed_channels = settings.discord_channel_ids

    def is_allowed(channel_id: int) -> bool:
        return not allowed_channels or channel_id in allowed_channels

    @client.event
    async def on_ready():
        logger.info(f"Discord bot connected as {client.user}")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        if not is_allowed(message.channel.id):
            return

        content = message.content.strip()
        if not content.startswith("!"):
            return

        parts = content.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler_entry = COMMANDS.get(cmd_name)
        if not handler_entry:
            return

        handler_fn, needs_args = handler_entry
        if needs_args:
            result = await handler_fn(args, SOURCE)
        else:
            result = await handler_fn(SOURCE)

        # Discord uses ** for bold instead of *
        text = result.text.replace("*", "**") if result.parse_mode == "Markdown" else result.text
        await message.reply(text)

    logger.info("Starting Discord bot...")
    await client.start(settings.discord_bot_token)
