"""Example Plugin — logs events to demonstrate the plugin system."""

import logging

logger = logging.getLogger(__name__)


def on_event(event_type: str, data: dict):
    """Handle an event from Mission Control."""
    logger.info(f"[example_plugin] Received {event_type}: {data}")
