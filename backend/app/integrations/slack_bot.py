"""
Slack Bot Integration

Thin adapter over the shared command layer. All business logic
lives in commands.py — this file only handles Slack-specific
message routing and bot lifecycle.

Uses Socket Mode so no public URL is needed.
"""

import logging

from app.config import settings
from app.integrations.commands import (
    cmd_task, cmd_idea, cmd_note, cmd_status, cmd_run,
    cmd_projects, cmd_approve, cmd_help,
)

logger = logging.getLogger(__name__)

SOURCE = "slack"

# Map /command names to (handler_fn, needs_args)
COMMANDS = {
    "/task": (cmd_task, True),
    "/idea": (cmd_idea, True),
    "/note": (cmd_note, True),
    "/approve": (cmd_approve, True),
    "/status": (cmd_status, False),
    "/run": (cmd_run, True),
    "/projects": (cmd_projects, False),
    "/help": (cmd_help, False),
}


async def start_slack_bot():
    """Start the Slack bot in Socket Mode."""
    if not settings.slack_bot_token or not settings.slack_app_token:
        logger.info("Slack bot not configured, skipping")
        return

    try:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    except ImportError:
        logger.warning(
            "slack_bolt not installed — pip install slack-bolt"
        )
        return

    slack_app = AsyncApp(token=settings.slack_bot_token)

    async def _handle_command(command_name: str, args: str) -> str:
        """Dispatch a command name to the shared handler and return text."""
        handler_entry = COMMANDS.get(command_name)
        if not handler_entry:
            return f"Unknown command: {command_name}"

        handler_fn, needs_args = handler_entry
        if needs_args:
            result = await handler_fn(args, SOURCE)
        else:
            result = await handler_fn(SOURCE)

        return result.text

    # Register each slash command with Slack
    @slack_app.command("/task")
    async def handle_task(ack, command):
        await ack()
        text = await _handle_command("/task", command.get("text", ""))
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/idea")
    async def handle_idea(ack, command):
        await ack()
        text = await _handle_command("/idea", command.get("text", ""))
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/note")
    async def handle_note(ack, command):
        await ack()
        text = await _handle_command("/note", command.get("text", ""))
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/status")
    async def handle_status(ack, command):
        await ack()
        text = await _handle_command("/status", "")
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/run")
    async def handle_run(ack, command):
        await ack()
        text = await _handle_command("/run", command.get("text", ""))
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/projects")
    async def handle_projects(ack, command):
        await ack()
        text = await _handle_command("/projects", "")
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/approve")
    async def handle_approve(ack, command):
        await ack()
        text = await _handle_command("/approve", command.get("text", ""))
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    @slack_app.command("/help")
    async def handle_help(ack, command):
        await ack()
        text = await _handle_command("/help", "")
        await slack_app.client.chat_postMessage(
            channel=command["channel_id"], text=text,
        )

    logger.info("Starting Slack bot (Socket Mode)...")
    handler = AsyncSocketModeHandler(slack_app, settings.slack_app_token)
    await handler.start_async()
