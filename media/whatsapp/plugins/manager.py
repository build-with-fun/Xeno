"""Plugin manager: loads, configures, and executes plugins."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from typing import Optional

from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from .base import Plugin, PluginContext, PluginResult, HookPoint

logger = get_logger(__name__)


class PluginManager:
    """Manages plugin lifecycle and execution."""

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []
        self._lock = threading.RLock()
        self._initialized = False

    def load_builtin(self) -> None:
        """Auto-discover and load all plugins in plugins/builtin/."""
        if self._initialized:
            return
        self._initialized = True
        try:
            import media.whatsapp.plugins.builtin as builtin_pkg
            for importer, modname, ispkg in pkgutil.iter_modules(builtin_pkg.__path__):
                try:
                    module = importlib.import_module(f"plugins.builtin.{modname}")
                    # Find the Plugin subclass in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, Plugin) and obj is not Plugin
                                and obj.__module__ == module.__name__):
                            # Load config from DB
                            config = self._load_config(obj.name)
                            plugin = obj(config=config)
                            self.register(plugin)
                            logger.info(f"[Plugins] Loaded: {plugin.name} v{plugin.version}")
                except Exception as e:
                    logger.warning(f"[Plugins] Failed to load {modname}: {e}")
        except Exception as e:
            logger.warning(f"[Plugins] Could not load builtin plugins: {e}")

    def _load_config(self, plugin_name: str) -> dict:
        """Load plugin config from the database."""
        try:
            from media.whatsapp.db.repo import PluginStateRepo
            state = PluginStateRepo.get(plugin_name)
            if state and state.config:
                return state.config
        except Exception:
            pass
        return {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        with self._lock:
            self._plugins.append(plugin)

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name."""
        with self._lock:
            before = len(self._plugins)
            self._plugins = [p for p in self._plugins if p.name != name]
            return len(self._plugins) < before

    def get(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        with self._lock:
            for p in self._plugins:
                if p.name == name:
                    return p
        return None

    def list_plugins(self) -> list[dict]:
        """List all registered plugins."""
        with self._lock:
            return [
                {
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "hooks": [h.value for h in p.hooks],
                    "config": p.config,
                }
                for p in self._plugins
            ]

    def execute_hook(self, hook: HookPoint, ctx: PluginContext) -> PluginResult:
        """Execute all plugins registered for the given hook.

        Plugins run in registration order. If any plugin returns
        stop_processing=True, remaining plugins are skipped.
        """
        combined = PluginResult()
        with self._lock:
            plugins = list(self._plugins)

        for plugin in plugins:
            if hook not in plugin.hooks:
                continue
            try:
                fn = getattr(plugin, hook.value, None)
                if fn is None:
                    continue
                start = __import__("time").time()
                result = fn(ctx)
                elapsed = (__import__("time").time() - start) * 1000
                metrics.observe("plugin_latency_ms", elapsed,
                                plugin=plugin.name, hook=hook.value)
                metrics.inc("plugin_executions", plugin=plugin.name, hook=hook.value)

                # Merge results
                if result.stop_processing:
                    combined.stop_processing = True
                    break
                if result.skip_reply:
                    combined.skip_reply = True
                if result.modified_messages:
                    ctx.messages = result.modified_messages
                    combined.modified_messages = result.modified_messages
                if result.modified_decision:
                    ctx.decision = result.modified_decision
                    combined.modified_decision = result.modified_decision
                if result.modified_reply is not None:
                    ctx.reply = result.modified_reply
                    combined.modified_reply = result.modified_reply
                combined.metadata.update(result.metadata)
            except Exception as e:
                logger.error(f"[Plugins] {plugin.name}.{hook.value} error: {e}")
                metrics.inc("plugin_errors", plugin=plugin.name, hook=hook.value)

        return combined

    @property
    def plugins(self) -> list[Plugin]:
        with self._lock:
            return list(self._plugins)


# Singleton
plugin_manager = PluginManager()
