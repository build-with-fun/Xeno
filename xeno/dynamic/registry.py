"""Central dynamic registry — connects all dynamic systems.

The DynamicRegistry is the single source of truth for:
- Discovered agents
- Loaded plugins
- Registered tools
- MCP servers
- Skills
- Agent hooks
- Configuration

Everything is hot-reloadable. The registry provides:
- Unified API for adding/removing components
- Event broadcasting when components change
- Conflict resolution
- Health monitoring
- Export/import of full state
"""

from __future__ import annotations

import json
import logging
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    name: str
    component_type: str  # agent, tool, mcp, plugin, skill
    healthy: bool = True
    last_check: float = field(default_factory=time.time)
    error: Optional[str] = None
    reload_count: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "type": self.component_type,
            "healthy": self.healthy, "last_check": self.last_check,
            "error": self.error, "reloads": self.reload_count,
        }


class DynamicRegistry:
    """Central hub for all dynamic components.

    Manages:
    - Agent discovery and registration
    - Tool registration (built-in + plugin + dynamic)
    - MCP server management
    - Plugin lifecycle
    - Skill management
    - Hook orchestration
    - Health monitoring
    - Event broadcasting
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/dynamic")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Component stores
        self.agents: dict[str, Any] = {}  # id -> AgentDescriptor
        self.tools: dict[str, Any] = {}  # name -> tool_func
        self.tool_schemas: dict[str, dict] = {}  # name -> schema
        self.mcp_servers: dict[str, dict] = {}  # name -> config
        self.skills: dict[str, Any] = {}  # name -> skill_data
        self.hooks: dict[str, list[Callable]] = {}  # event_name -> [callbacks]
        self.health: dict[str, ComponentHealth] = {}

        # Config
        self.config: dict[str, Any] = {}
        self._config_callbacks: list[Callable] = []

        # Thread safety
        self._lock = threading.Lock()

        # Discovery references (set by init)
        self._agent_discovery = None
        self._plugin_loader = None
        self._hotreload = None

        # Load persisted state
        self._load_state()

    # --- Agent management ---

    def register_agent(self, agent_id: str, descriptor: Any) -> None:
        with self._lock:
            self.agents[agent_id] = descriptor
            self.health[agent_id] = ComponentHealth(
                name=agent_id, component_type="agent",
            )
        self._broadcast("agent_registered", {"id": agent_id})
        self._save_state()

    def unregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                self.health.pop(agent_id, None)
        self._broadcast("agent_unregistered", {"id": agent_id})
        self._save_state()
        return True

    def get_agent(self, agent_id: str) -> Any:
        return self.agents.get(agent_id)

    def list_agents(self, enabled_only: bool = True) -> list[Any]:
        agents = list(self.agents.values())
        if enabled_only:
            agents = [a for a in agents if getattr(a, "enabled", True)]
        return agents

    def reload_agent(self, agent_id: str) -> bool:
        if self._agent_discovery:
            result = self._agent_discovery.reload_agent(agent_id)
            if result:
                self.agents[agent_id] = result
                if agent_id in self.health:
                    self.health[agent_id].reload_count += 1
                    self.health[agent_id].last_check = time.time()
                self._broadcast("agent_reloaded", {"id": agent_id})
                return True
        return False

    # --- Tool management ---

    def register_tool(self, name: str, func: Any, schema: Optional[dict] = None, source: str = "builtin") -> None:
        with self._lock:
            self.tools[name] = func
            if schema:
                self.tool_schemas[name] = schema
            self.health[f"tool_{name}"] = ComponentHealth(
                name=name, component_type="tool",
            )
        self._broadcast("tool_registered", {"name": name, "source": source})
        logger.info(f"Tool registered: {name} (from {source})")

    def unregister_tool(self, name: str) -> bool:
        with self._lock:
            if name in self.tools:
                del self.tools[name]
                self.tool_schemas.pop(name, None)
                self.health.pop(f"tool_{name}", None)
        self._broadcast("tool_unregistered", {"name": name})
        return True

    def get_tool(self, name: str) -> Any:
        return self.tools.get(name)

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "schema": self.tool_schemas.get(name, {})}
            for name in self.tools
        ]

    def get_all_tool_functions(self) -> list[Any]:
        """Return all registered tool functions (for passing to the agent)."""
        return list(self.tools.values())

    def register_tools_from_module(self, module: Any, source: str = "module") -> int:
        """Auto-discover and register tools from a Python module."""
        count = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.startswith("_"):
                if hasattr(attr, "__wrapped__") or (hasattr(attr, "__doc__") and getattr(attr, "__doc__", "")):
                    tool_name = getattr(attr, "tool_name", attr_name)
                    self.register_tool(tool_name, attr, source=source)
                    count += 1
        return count

    # --- MCP management ---

    def register_mcp_server(self, name: str, config: dict) -> None:
        with self._lock:
            self.mcp_servers[name] = config
            self.health[f"mcp_{name}"] = ComponentHealth(
                name=name, component_type="mcp",
            )
        self._broadcast("mcp_registered", {"name": name})
        self._save_state()

    def unregister_mcp_server(self, name: str) -> bool:
        with self._lock:
            if name in self.mcp_servers:
                del self.mcp_servers[name]
                self.health.pop(f"mcp_{name}", None)
        self._broadcast("mcp_unregistered", {"name": name})
        self._save_state()
        return True

    def get_mcp_server(self, name: str) -> Optional[dict]:
        return self.mcp_servers.get(name)

    def list_mcp_servers(self) -> list[dict]:
        return [{"name": k, **v} for k, v in self.mcp_servers.items()]

    # --- Skill management ---

    def register_skill(self, name: str, skill_data: Any) -> None:
        with self._lock:
            self.skills[name] = skill_data
        self._broadcast("skill_registered", {"name": name})

    def unregister_skill(self, name: str) -> bool:
        with self._lock:
            if name in self.skills:
                del self.skills[name]
        self._broadcast("skill_unregistered", {"name": name})
        return True

    def get_skill(self, name: str) -> Any:
        return self.skills.get(name)

    def list_skills(self) -> list[str]:
        return list(self.skills.keys())

    # --- Hook system ---

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a hook callback for an event."""
        self.hooks.setdefault(event_name, []).append(callback)

    def off(self, event_name: str, callback: Optional[Callable] = None) -> None:
        """Remove hook(s) for an event."""
        if callback:
            self.hooks[event_name] = [c for c in self.hooks.get(event_name, []) if c != callback]
        else:
            self.hooks.pop(event_name, None)

    def _broadcast(self, event_name: str, data: Any) -> None:
        """Broadcast an event to all registered hooks."""
        for cb in self.hooks.get(event_name, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"Hook error on '{event_name}': {e}")
        # Also fire wildcard
        for cb in self.hooks.get("*", []):
            try:
                cb(event_name, data)
            except Exception:
                pass

    # --- Config management ---

    def update_config(self, key: str, value: Any) -> None:
        """Update a config value and notify watchers."""
        with self._lock:
            self.config[key] = value
        for cb in self._config_callbacks:
            try:
                cb(key, value)
            except Exception:
                pass
        self._broadcast("config_updated", {"key": key, "value": value})
        self._save_state()

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def on_config_change(self, callback: Callable) -> None:
        self._config_callbacks.append(callback)

    # --- Health monitoring ---

    def check_health(self) -> dict[str, Any]:
        """Run health checks on all components."""
        healthy = 0
        unhealthy = 0
        for name, h in self.health.items():
            if h.healthy:
                healthy += 1
            else:
                unhealthy += 1
        return {
            "total": len(self.health),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "components": {name: h.to_dict() for name, h in self.health.items()},
        }

    def mark_unhealthy(self, name: str, error: str) -> None:
        if name in self.health:
            self.health[name].healthy = False
            self.health[name].error = error
            self.health[name].last_check = time.time()

    def mark_healthy(self, name: str) -> None:
        if name in self.health:
            self.health[name].healthy = True
            self.health[name].error = None
            self.health[name].last_check = time.time()

    # --- Full reload ---

    def reload_all(self) -> dict[str, int]:
        """Reload all dynamic components from disk."""
        counts = {"agents": 0, "plugins": 0, "tools": 0}
        if self._agent_discovery:
            agents = self._agent_discovery.scan()
            for a in agents:
                self.register_agent(a.id, a)
            counts["agents"] = len(agents)
        if self._plugin_loader:
            plugins = self._plugin_loader.scan_and_load()
            for p in plugins:
                if p.tools:
                    for tool in p.tools:
                        name = getattr(tool, "__name__", str(tool))
                        self.register_tool(name, tool, source=f"plugin:{p.metadata.name}")
            counts["plugins"] = len(plugins)
        self._broadcast("full_reload", counts)
        logger.info(f"Full reload: {counts}")
        return counts

    # --- Persistence ---

    def export_state(self) -> dict:
        """Export the full registry state."""
        return {
            "agents": {k: v.to_dict() if hasattr(v, "to_dict") else str(v) for k, v in self.agents.items()},
            "tools": list(self.tools.keys()),
            "mcp_servers": dict(self.mcp_servers),
            "skills": {k: str(v)[:200] for k, v in self.skills.items()},
            "config": dict(self.config),
            "health": {k: v.to_dict() for k, v in self.health.items()},
            "exported_at": time.time(),
        }

    def _save_state(self) -> None:
        """Persist registry state to disk."""
        try:
            state = {
                "mcp_servers": self.mcp_servers,
                "config": self.config,
                "agents": {
                    k: v.to_dict() if hasattr(v, "to_dict") else {"name": str(v)}
                    for k, v in self.agents.items()
                },
                "saved_at": time.time(),
            }
            (self.data_dir / "registry_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.error(f"Failed to save registry state: {e}")

    def _load_state(self) -> None:
        """Load persisted registry state."""
        path = self.data_dir / "registry_state.json"
        if path.exists():
            try:
                state = json.loads(path.read_text())
                self.mcp_servers = state.get("mcp_servers", {})
                self.config = state.get("config", {})
            except Exception:
                pass

    # --- Summary ---

    def summary(self) -> dict[str, Any]:
        return {
            "agents": len(self.agents),
            "tools": len(self.tools),
            "mcp_servers": len(self.mcp_servers),
            "skills": len(self.skills),
            "hooks": sum(len(v) for v in self.hooks.values()),
            "health": self.check_health(),
        }

    def full_summary(self) -> str:
        s = self.summary()
        return (
            f"Dynamic Registry: {s['agents']} agents, {s['tools']} tools, "
            f"{s['mcp_servers']} MCP servers, {s['skills']} skills, "
            f"{s['hooks']} hooks | Health: {s['health']['healthy']}/{s['health']['total']} OK"
        )
