"""Dynamic plugin loader system.

Auto-discovers and loads Python plugins from:
- plugins/ directory at project root
- Any configured plugin directory
- Entry points (pip installable plugins)
- Remote plugin URLs (future)

Plugin structure:
  plugins/
    my_plugin/
      __init__.py      <- must export: def register(registry) -> PluginHooks
      plugin.json      <- optional metadata
    another_plugin.py  <- single-file plugin

plugin.json format:
  {
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "...",
    "author": "...",
    "hooks": ["before_tool", "after_tool", "on_memory_store"],
    "tools": ["my_custom_tool"],
    "mcp_servers": ["my_mcp_server"]
  }

Plugin __init__.py must export:
  def register(registry) -> dict:
      return {
          "hooks": {...},
          "tools": [...],
          "mcp_servers": {...},
      }
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    name: str
    version: str = "0.0.1"
    description: str = ""
    author: str = ""
    hooks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    enabled: bool = True
    folder_path: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = ""
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    when_to_use: str = ""
    priority: int = 50
    cost: str = "free"

    def to_dict(self) -> dict:
        return {
            "name": self.name, "version": self.version,
            "description": self.description, "author": self.author,
            "hooks": self.hooks, "tools": self.tools,
            "mcp_servers": self.mcp_servers, "enabled": self.enabled,
            "tags": self.tags, "category": self.category,
            "capabilities": self.capabilities, "dependencies": self.dependencies,
            "when_to_use": self.when_to_use, "priority": self.priority,
            "cost": self.cost,
        }


@dataclass
class PluginHooks:
    """Hooks provided by a plugin."""
    before_tool: Optional[Callable] = None
    after_tool: Optional[Callable] = None
    on_memory_store: Optional[Callable] = None
    on_memory_retrieve: Optional[Callable] = None
    on_agent_start: Optional[Callable] = None
    on_agent_end: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_chat_message: Optional[Callable] = None
    on_config_load: Optional[Callable] = None
    custom: dict[str, Callable] = field(default_factory=dict)


@dataclass
class LoadedPlugin:
    metadata: PluginMetadata
    hooks: PluginHooks
    module: Any = None
    tools: list[Any] = field(default_factory=list)
    mcp_servers: dict[str, dict] = field(default_factory=dict)
    loaded_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "loaded_at": self.loaded_at,
            "error": self.error,
            "tools_count": len(self.tools),
        }


class PluginLoader:
    """Discovers, loads, and manages plugins.

    Supports:
    - Directory-based plugins (plugin folder with __init__.py)
    - Single-file plugins (.py files)
    - plugin.json metadata
    - Hot-reload on file changes
    - Plugin enable/disable
    """

    def __init__(self, plugin_dirs: Optional[list[str]] = None):
        self.plugin_dirs = plugin_dirs or []
        self.plugins: dict[str, LoadedPlugin] = {}
        self._file_mtimes: dict[str, float] = {}
        self._registry_ref: Any = None

    def set_registry(self, registry: Any) -> None:
        """Set reference to the dynamic registry for plugin registration."""
        self._registry_ref = registry

    def add_plugin_dir(self, directory: str) -> None:
        if directory not in self.plugin_dirs:
            self.plugin_dirs.append(directory)

    def scan_and_load(self) -> list[LoadedPlugin]:
        """Scan all plugin directories and load discovered plugins."""
        loaded = []
        for plugin_dir in self.plugin_dirs:
            dir_path = Path(plugin_dir)
            if not dir_path.exists():
                continue
            for entry in sorted(dir_path.iterdir()):
                if entry.name.startswith((".", "_")):
                    continue
                if entry.is_dir():
                    plugin = self._load_directory_plugin(entry)
                    if plugin:
                        loaded.append(plugin)
                elif entry.suffix == ".py":
                    plugin = self._load_single_file_plugin(entry)
                    if plugin:
                        loaded.append(plugin)
        return loaded

    def _load_directory_plugin(self, folder: Path) -> Optional[LoadedPlugin]:
        """Load a plugin from a directory with __init__.py."""
        init_file = folder / "__init__.py"
        if not init_file.exists():
            return None

        # Parse metadata
        metadata = self._parse_plugin_json(folder / "plugin.json", folder.name)

        # Load module
        module_name = f"xeno_plugin_{folder.name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(init_file))
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Call register function
            hooks = PluginHooks()
            tools = []
            mcp_servers = {}

            if hasattr(module, "register"):
                result = module.register(self._registry_ref)
                if isinstance(result, dict):
                    h = result.get("hooks", {})
                    if isinstance(h, dict):
                        hooks.before_tool = h.get("before_tool")
                        hooks.after_tool = h.get("after_tool")
                        hooks.on_memory_store = h.get("on_memory_store")
                        hooks.on_memory_retrieve = h.get("on_memory_retrieve")
                        hooks.on_agent_start = h.get("on_agent_start")
                        hooks.on_agent_end = h.get("on_agent_end")
                        hooks.on_error = h.get("on_error")
                        hooks.on_chat_message = h.get("on_chat_message")
                        hooks.custom = {k: v for k, v in h.items()
                                        if k not in ("before_tool", "after_tool", "on_memory_store",
                                                     "on_memory_retrieve", "on_agent_start", "on_agent_end",
                                                     "on_error", "on_chat_message")}
                    tools = result.get("tools", [])
                    mcp_servers = result.get("mcp_servers", {})

            plugin = LoadedPlugin(
                metadata=metadata, hooks=hooks, module=module,
                tools=tools, mcp_servers=mcp_servers,
            )
            self.plugins[metadata.name] = plugin
            self._file_mtimes[str(init_file)] = init_file.stat().st_mtime
            logger.info(f"Loaded plugin: {metadata.name} v{metadata.version}")
            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin {folder.name}: {e}")
            plugin = LoadedPlugin(
                metadata=metadata, hooks=PluginHooks(), error=str(e),
            )
            self.plugins[metadata.name] = plugin
            return plugin

    def _load_single_file_plugin(self, file_path: Path) -> Optional[LoadedPlugin]:
        """Load a single .py file as a plugin."""
        plugin_name = file_path.stem
        metadata = PluginMetadata(
            name=plugin_name, description=f"Single-file plugin: {plugin_name}",
            folder_path=str(file_path),
        )
        module_name = f"xeno_plugin_{plugin_name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            hooks = PluginHooks()
            tools = []
            if hasattr(module, "register"):
                result = module.register(self._registry_ref)
                if isinstance(result, dict):
                    h = result.get("hooks", {})
                    if isinstance(h, dict):
                        hooks.before_tool = h.get("before_tool")
                        hooks.after_tool = h.get("after_tool")
                    tools = result.get("tools", [])

            plugin = LoadedPlugin(metadata=metadata, hooks=hooks, module=module, tools=tools)
            self.plugins[plugin_name] = plugin
            self._file_mtimes[str(file_path)] = file_path.stat().st_mtime
            return plugin
        except Exception as e:
            logger.error(f"Failed to load single-file plugin {file_path}: {e}")
            return None

    def _parse_plugin_json(self, path: Path, fallback_name: str) -> PluginMetadata:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return PluginMetadata(
                    name=data.get("name", fallback_name),
                    version=data.get("version", "0.0.1"),
                    description=data.get("description", ""),
                    author=data.get("author", ""),
                    hooks=data.get("hooks", []),
                    tools=data.get("tools", []),
                    mcp_servers=data.get("mcp_servers", []),
                    enabled=data.get("enabled", True),
                    tags=data.get("tags", []),
                    category=data.get("category", ""),
                    capabilities=data.get("capabilities", []),
                    dependencies=data.get("dependencies", []),
                    when_to_use=data.get("when_to_use", ""),
                    priority=int(data.get("priority", 50)),
                    cost=data.get("cost", "free"),
                )
            except Exception:
                pass
        return PluginMetadata(name=fallback_name)

    def get_plugin(self, name: str) -> Optional[LoadedPlugin]:
        return self.plugins.get(name)

    def list_plugins(self, enabled_only: bool = True) -> list[LoadedPlugin]:
        plugins = list(self.plugins.values())
        if enabled_only:
            plugins = [p for p in plugins if p.metadata.enabled]
        return plugins

    def enable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin:
            plugin.metadata.enabled = True
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin:
            plugin.metadata.enabled = False
            return True
        return False

    def unload_plugin(self, name: str) -> bool:
        if name in self.plugins:
            plugin = self.plugins[name]
            if plugin.module:
                module_name = plugin.module.__name__
                sys.modules.pop(module_name, None)
            del self.plugins[name]
            return True
        return False

    def reload_plugin(self, name: str) -> Optional[LoadedPlugin]:
        plugin = self.plugins.get(name)
        if not plugin:
            return None
        folder_path = Path(plugin.metadata.folder_path)
        self.unload_plugin(name)
        if folder_path.is_dir():
            return self._load_directory_plugin(folder_path)
        elif folder_path.is_file():
            return self._load_single_file_plugin(folder_path)
        return None

    def check_for_updates(self) -> list[str]:
        changed = []
        for name, plugin in self.plugins.items():
            init_path = Path(plugin.metadata.folder_path)
            if init_path.is_dir():
                init_path = init_path / "__init__.py"
            if init_path.exists():
                current_mtime = init_path.stat().st_mtime
                old_mtime = self._file_mtimes.get(str(init_path), 0)
                if current_mtime > old_mtime:
                    changed.append(name)
        return changed

    def get_all_tools(self) -> list[Any]:
        """Get all tools provided by all plugins."""
        all_tools = []
        for plugin in self.plugins.values():
            if plugin.metadata.enabled:
                all_tools.extend(plugin.tools)
        return all_tools

    def get_all_mcp_servers(self) -> dict[str, dict]:
        """Get all MCP server configs from all plugins."""
        all_servers = {}
        for plugin in self.plugins.values():
            if plugin.metadata.enabled:
                all_servers.update(plugin.mcp_servers)
        return all_servers

    def summary(self) -> str:
        enabled = sum(1 for p in self.plugins.values() if p.metadata.enabled)
        total_tools = sum(len(p.tools) for p in self.plugins.values())
        return f"Plugins: {enabled}/{len(self.plugins)} enabled, {total_tools} tools contributed"
