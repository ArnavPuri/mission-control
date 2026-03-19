"""
Plugin Loader

Scans the `plugins/` directory for Python packages with a `plugin.yaml` manifest.
Each plugin can register event handlers that fire on EventLog entries.

Manifest format (plugin.yaml):
    name: example-plugin
    version: "1.0.0"
    description: An example plugin
    author: Your Name
    hooks:
      - task.created
      - idea.created
"""

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

import yaml

logger = logging.getLogger(__name__)

# Type alias for plugin event handlers
EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class PluginManifest:
    """Parsed plugin.yaml manifest."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    hooks: list[str] = field(default_factory=list)


@dataclass
class PluginInfo:
    """Runtime state for a loaded plugin."""
    manifest: PluginManifest
    module: Any  # The imported Python module
    enabled: bool = True
    handlers: dict[str, list[EventHandler]] = field(default_factory=dict)


class PluginLoader:
    """Discovers, loads, and manages plugins from a directory."""

    def __init__(self, plugins_dir: str | Path = "plugins") -> None:
        self._plugins_dir = Path(plugins_dir)
        self._plugins: dict[str, PluginInfo] = {}

    @property
    def plugins(self) -> dict[str, PluginInfo]:
        return self._plugins

    async def discover_and_load(self) -> None:
        """Scan the plugins directory and load all valid plugins."""
        if not self._plugins_dir.exists():
            logger.info(f"Plugins directory {self._plugins_dir} does not exist, skipping")
            return

        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "plugin.yaml"
            init_path = entry / "__init__.py"

            if not manifest_path.exists():
                logger.debug(f"Skipping {entry.name}: no plugin.yaml")
                continue
            if not init_path.exists():
                logger.debug(f"Skipping {entry.name}: no __init__.py")
                continue

            try:
                await self._load_plugin(entry, manifest_path)
            except Exception as e:
                logger.error(f"Failed to load plugin from {entry.name}: {e}", exc_info=True)

        loaded = [p.manifest.name for p in self._plugins.values()]
        logger.info(f"Loaded {len(loaded)} plugin(s): {', '.join(loaded) or 'none'}")

    async def _load_plugin(self, plugin_dir: Path, manifest_path: Path) -> None:
        """Load a single plugin from its directory."""
        # Parse manifest
        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        manifest = PluginManifest(
            name=raw.get("name", plugin_dir.name),
            version=raw.get("version", "0.0.0"),
            description=raw.get("description", ""),
            author=raw.get("author", ""),
            hooks=raw.get("hooks", []),
        )

        # Import the plugin module
        module_name = f"plugins.{plugin_dir.name}"
        spec = importlib.util.spec_from_file_location(
            module_name, plugin_dir / "__init__.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {plugin_dir}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Build handler map
        handlers: dict[str, list[EventHandler]] = {}
        for hook in manifest.hooks:
            handler_fn = getattr(module, "on_event", None)
            if handler_fn is not None:
                handlers.setdefault(hook, []).append(handler_fn)

            # Also check for hook-specific handlers: on_task_created, on_idea_created, etc.
            specific_name = "on_" + hook.replace(".", "_")
            specific_fn = getattr(module, specific_name, None)
            if specific_fn is not None:
                handlers.setdefault(hook, []).append(specific_fn)

        plugin_info = PluginInfo(
            manifest=manifest,
            module=module,
            enabled=True,
            handlers=handlers,
        )

        # Call plugin's setup function if it exists
        setup_fn = getattr(module, "setup", None)
        if setup_fn is not None:
            result = setup_fn()
            # Support async setup
            if hasattr(result, "__await__"):
                await result

        self._plugins[manifest.name] = plugin_info
        logger.info(
            f"Loaded plugin: {manifest.name} v{manifest.version} "
            f"(hooks: {', '.join(manifest.hooks) or 'none'})"
        )

    async def fire_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Fire an event to all plugins that registered for it.

        Args:
            event_type: The event type, e.g. "task.created".
            data: Event payload (typically the EventLog row as a dict).
        """
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            handlers = plugin.handlers.get(event_type, [])
            for handler in handlers:
                try:
                    await handler(event_type, data)
                except Exception as e:
                    logger.error(
                        f"Plugin {plugin.manifest.name} handler error "
                        f"for {event_type}: {e}",
                        exc_info=True,
                    )

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin by name. Returns True if found."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.enabled = True
        logger.info(f"Plugin enabled: {name}")
        return True

    # Alias for API compatibility
    enable = enable_plugin

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin by name. Returns True if found."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        plugin.enabled = False
        logger.info(f"Plugin disabled: {name}")
        return True

    # Alias for API compatibility
    disable = disable_plugin

    def load_plugins(self) -> None:
        """Synchronous plugin discovery and loading.

        Scans the plugins directory and loads all valid plugins.
        Suitable for calling from startup code where async is not needed
        for the initial load.
        """
        if not self._plugins_dir.exists():
            logger.info(f"Plugins directory {self._plugins_dir} does not exist, skipping")
            return

        for entry in sorted(self._plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "plugin.yaml"
            init_path = entry / "__init__.py"

            if not manifest_path.exists() or not init_path.exists():
                continue

            try:
                self._load_plugin_sync(entry, manifest_path)
            except Exception as e:
                logger.error(f"Failed to load plugin from {entry.name}: {e}", exc_info=True)

        loaded = [p.manifest.name for p in self._plugins.values()]
        logger.info(f"Loaded {len(loaded)} plugin(s): {', '.join(loaded) or 'none'}")

    def _load_plugin_sync(self, plugin_dir: Path, manifest_path: Path) -> None:
        """Synchronously load a single plugin."""
        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        manifest = PluginManifest(
            name=raw.get("name", plugin_dir.name),
            version=raw.get("version", "0.0.0"),
            description=raw.get("description", ""),
            author=raw.get("author", ""),
            hooks=raw.get("hooks", []),
        )

        module_name = f"plugins.{plugin_dir.name}"
        spec = importlib.util.spec_from_file_location(
            module_name, plugin_dir / "__init__.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {plugin_dir}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        handlers: dict[str, list[EventHandler]] = {}
        for hook in manifest.hooks:
            handler_fn = getattr(module, "on_event", None)
            if handler_fn is not None:
                handlers.setdefault(hook, []).append(handler_fn)
            specific_name = "on_" + hook.replace(".", "_")
            specific_fn = getattr(module, specific_name, None)
            if specific_fn is not None:
                handlers.setdefault(hook, []).append(specific_fn)

        plugin_info = PluginInfo(
            manifest=manifest,
            module=module,
            enabled=True,
            handlers=handlers,
        )

        setup_fn = getattr(module, "setup", None)
        if setup_fn is not None:
            setup_fn()

        self._plugins[manifest.name] = plugin_info
        logger.info(
            f"Loaded plugin: {manifest.name} v{manifest.version} "
            f"(hooks: {', '.join(manifest.hooks) or 'none'})"
        )

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return info about all loaded plugins."""
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "author": p.manifest.author,
                "hooks": p.manifest.hooks,
                "enabled": p.enabled,
            }
            for p in self._plugins.values()
        ]


# Global plugin loader instance
plugin_loader = PluginLoader()
plugin_manager = plugin_loader  # Alias used by the plugins API
