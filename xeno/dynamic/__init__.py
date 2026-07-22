"""Dynamic system — auto-discovery and hot-reload for everything.

Coordinates:
- Agent discovery from agents/, media/, custom dirs
- Plugin loading from plugins/
- MCP server auto-config
- Skill auto-loading
- Hot-reload watching
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from xeno.dynamic.discovery import AgentDiscovery, AgentDescriptor
from xeno.dynamic.plugins import PluginLoader
from xeno.dynamic.hotreload import HotReloadWatcher
from xeno.dynamic.registry import DynamicRegistry

logger = logging.getLogger(__name__)


class DynamicSystem:
    """Master coordinator for all dynamic components.

    Usage:
        ds = DynamicSystem(config)
        ds.start()  # scan, load, watch
        agents = ds.discovered_agents
        tools = ds.registry.get_all_tool_functions()
    """

    def __init__(self, config: Any = None):
        self.config = config
        self._data_dir: Path = Path("data/dynamic")

        # Core components
        self.registry = DynamicRegistry(self._data_dir)
        self.agent_discovery = AgentDiscovery()
        self.plugin_loader = PluginLoader()
        self.watcher = HotReloadWatcher()

        # Wire them together
        self.registry._agent_discovery = self.agent_discovery
        self.registry._plugin_loader = self.plugin_loader
        self.registry._hotreload = self.watcher
        self.plugin_loader.set_registry(self.registry)

        # State
        self.discovered_agents: dict[str, AgentDescriptor] = {}
        self._running = False

    def configure(self, config: Any) -> None:
        """Configure scan directories from XenoConfig."""
        self.config = config
        self._data_dir = Path(config.data_dir) / "dynamic" if hasattr(config, "data_dir") else Path("data/dynamic")
        self.registry.data_dir = self._data_dir

        # Default scan directories
        project_root = Path(config.project_root) if hasattr(config, "project_root") else Path.cwd()
        self.agent_discovery.add_scan_dir(str(project_root / "agents"))
        self.agent_discovery.add_scan_dir(str(project_root / "media"))

        # Plugin directories
        self.plugin_loader.add_plugin_dir(str(project_root / "plugins"))

        # Custom directories from config
        if hasattr(config, "agent_dirs"):
            for d in config.agent_dirs:
                self.agent_discovery.add_scan_dir(d)
        if hasattr(config, "plugin_dirs"):
            for d in config.plugin_dirs:
                self.plugin_loader.add_plugin_dir(d)

    def start(self) -> None:
        """Start the dynamic system: scan, load, watch."""
        if self._running:
            return

        # 1. Scan for agents
        agents = self.agent_discovery.scan()
        for agent in agents:
            self.discovered_agents[agent.id] = agent
            self.registry.register_agent(agent.id, agent)
            # Load custom tools from agent's tools/ directory
            try:
                agent.load_custom_tools()
                if agent.custom_tools:
                    logger.info(f"Loaded {len(agent.custom_tools)} custom tools for agent {agent.name}")
            except Exception as e:
                logger.error(f"Failed to load custom tools for {agent.name}: {e}")
        logger.info(f"Discovered {len(agents)} agents")

        # 2. Load plugins
        plugins = self.plugin_loader.scan_and_load()
        for plugin in plugins:
            if plugin.tools:
                for tool in plugin.tools:
                    name = getattr(tool, "__name__", str(tool))
                    self.registry.register_tool(name, tool, source=f"plugin:{plugin.metadata.name}")
            if plugin.mcp_servers:
                for mcp_name, mcp_config in plugin.mcp_servers.items():
                    self.registry.register_mcp_server(mcp_name, mcp_config)
        logger.info(f"Loaded {len(plugins)} plugins")

        # 3. Set up hot-reload watches
        self._setup_watches()

        # 4. Start watcher
        self.watcher.start()
        self._running = True
        logger.info("Dynamic system started")

    def _setup_watches(self) -> None:
        """Set up file watches for all discovered components."""
        # Watch agent description.md files
        for agent in self.discovered_agents.values():
            desc_path = Path(agent.folder_path) / "description.md"
            if desc_path.exists():
                self.watcher.watch(
                    str(desc_path.parent),
                    "description.md",
                    self._on_agent_file_change,
                )

    def _on_agent_file_change(self, changed_path: str, event_type: str) -> None:
        """Handle agent file changes."""
        logger.info(f"Agent file changed: {changed_path} ({event_type})")
        folder = str(Path(changed_path).parent)
        for agent_id, agent in self.discovered_agents.items():
            if agent.folder_path == folder:
                reloaded = self.registry.reload_agent(agent_id)
                if reloaded:
                    self.discovered_agents[agent_id] = reloaded
                    logger.info(f"Hot-reloaded agent: {agent_id}")
                break

    def stop(self) -> None:
        """Stop the dynamic system."""
        self.watcher.stop()
        self._running = False
        logger.info("Dynamic system stopped")

    # --- Dynamic operations ---

    def add_agent_at_runtime(self, folder_path: str) -> Optional[AgentDescriptor]:
        """Add a new agent folder at runtime."""
        desc_path = Path(folder_path) / "description.md"
        if desc_path.exists():
            from xeno.dynamic.discovery import parse_description_md
            descriptor = parse_description_md(desc_path)
            self.discovered_agents[descriptor.id] = descriptor
            self.registry.register_agent(descriptor.id, descriptor)
            # Start watching
            self.watcher.watch(folder_path, "description.md", self._on_agent_file_change)
            return descriptor
        return None

    def add_mcp_server(self, name: str, server_type: str, command: list[str] = None,
                       url: str = "", env: dict = None, enabled: bool = True) -> None:
        """Add an MCP server configuration at runtime."""
        config = {"type": server_type, "enabled": enabled}
        if command:
            config["command"] = command
        if url:
            config["url"] = url
        if env:
            config["env"] = env
        self.registry.register_mcp_server(name, config)

    def remove_mcp_server(self, name: str) -> bool:
        return self.registry.unregister_mcp_server(name)

    def add_tool(self, name: str, func: Any, source: str = "runtime") -> None:
        """Register a new tool at runtime."""
        self.registry.register_tool(name, func, source=source)

    def remove_tool(self, name: str) -> bool:
        return self.registry.unregister_tool(name)

    def add_skill(self, name: str, content: str, skill_type: str = "general") -> None:
        """Register a skill at runtime."""
        self.registry.register_skill(name, {"content": content, "type": skill_type})

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "agents": len(self.discovered_agents),
            "registry": self.registry.summary(),
            "plugins": self.plugin_loader.summary(),
            "watcher": self.watcher.summary(),
        }
