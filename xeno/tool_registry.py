"""Dynamic tool registry for Xeno.

Follows the deepagents guide's "Tool Registry Pattern":
- Register/unregister tools at runtime
- Dynamic tool discovery and loading
- Tool versioning
- Tool health monitoring
- Hot-reload support
- Tool composition (chain tools)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Complete tool definition with metadata."""
    name: str
    description: str
    func: Callable
    parameters: dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    version: str = "1.0.0"
    enabled: bool = True
    requires_approval: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    call_count: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    _total_duration_ms: float = field(default=0.0, repr=False)

    def record_use(self, duration_ms: float, success: bool) -> None:
        """Record a tool usage."""
        self.call_count += 1
        self.last_used = time.time()
        if success:
            self._total_duration_ms += duration_ms
            self.avg_duration_ms = self._total_duration_ms / (self.call_count - self.error_count)
        else:
            self.error_count += 1

    def to_langchain_tool(self) -> Any:
        """Convert to a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool

        async def _run(**kwargs: Any) -> str:
            import time as _time
            start = _time.time()
            try:
                result = self.func(**kwargs)
                if hasattr(result, "__await__"):
                    result = await result
                duration = (_time.time() - start) * 1000
                self.record_use(duration, True)
                return str(result) if not isinstance(result, str) else result
            except Exception as e:
                duration = (_time.time() - start) * 1000
                self.record_use(duration, False)
                return f"Error: {e}"

        return StructuredTool(
            name=self.name,
            description=self.description,
            coroutine=_run,
            args_schema=self.parameters if self.parameters else None,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "enabled": self.enabled,
            "tags": self.tags,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
        }


class ToolRegistry:
    """Dynamic tool registry that manages tool lifecycle.

    Supports:
    - Register/unregister at runtime
    - Dynamic discovery from modules, directories, MCP servers
    - Tool health monitoring and stats
    - Hot-reload from config files
    - Tool composition
    """

    def __init__(self, config_dir: Optional[Path] = None):
        self.tools: dict[str, ToolDefinition] = {}
        self._categories: dict[str, set[str]] = {}
        self._config_dir = config_dir or Path("data/tools")
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Optional[dict] = None,
        category: str = "general",
        version: str = "1.0.0",
        tags: Optional[list[str]] = None,
        requires_approval: bool = False,
    ) -> ToolDefinition:
        """Register a tool."""
        if name in self.tools:
            logger.warning(f"Tool '{name}' already registered, updating")

        tool = ToolDefinition(
            name=name,
            description=description,
            func=func,
            parameters=parameters or {},
            category=category,
            version=version,
            tags=tags or [],
            requires_approval=requires_approval,
        )
        self.tools[name] = tool
        self._categories.setdefault(category, set()).add(name)
        logger.info(f"Registered tool: {name} v{version}")
        return tool

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name not in self.tools:
            return False
        tool = self.tools.pop(name)
        if tool.category in self._categories:
            self._categories[tool.category].discard(name)
        logger.info(f"Unregistered tool: {name}")
        return True

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self.tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self.tools

    def enable(self, name: str) -> bool:
        """Enable a tool."""
        tool = self.tools.get(name)
        if tool:
            tool.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool."""
        tool = self.tools.get(name)
        if tool:
            tool.enabled = False
            return True
        return False

    def list_tools(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[ToolDefinition]:
        """List tools with optional filters."""
        tools = list(self.tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def list_categories(self) -> dict[str, int]:
        """List categories with tool counts."""
        return {cat: len(tools) for cat, tools in self._categories.items()}

    def get_langchain_tools(self, enabled_only: bool = True) -> list[Any]:
        """Get all tools converted to LangChain format."""
        return [
            tool.to_langchain_tool()
            for tool in self.tools.values()
            if tool.enabled or not enabled_only
        ]

    def register_from_dict(self, tools_config: dict[str, dict]) -> int:
        """Register tools from a configuration dictionary."""
        count = 0
        for name, config in tools_config.items():
            if "func" in config:
                self.register(
                    name=name,
                    description=config.get("description", ""),
                    func=config["func"],
                    parameters=config.get("parameters"),
                    category=config.get("category", "general"),
                    version=config.get("version", "1.0.0"),
                    tags=config.get("tags", []),
                    requires_approval=config.get("requires_approval", False),
                )
                count += 1
        return count

    def save_config(self) -> None:
        """Save tool registry config to disk."""
        config = {}
        for name, tool in self.tools.items():
            config[name] = {
                "description": tool.description,
                "category": tool.category,
                "version": tool.version,
                "enabled": tool.enabled,
                "tags": tool.tags,
                "requires_approval": tool.requires_approval,
                "parameters": tool.parameters,
            }
        path = self._config_dir / "registry.json"
        path.write_text(json.dumps(config, indent=2))

    def load_config(self) -> int:
        """Load tool config from disk (re-enable/disable)."""
        path = self._config_dir / "registry.json"
        if not path.exists():
            return 0
        try:
            config = json.loads(path.read_text())
            count = 0
            for name, settings in config.items():
                if name in self.tools:
                    self.tools[name].enabled = settings.get("enabled", True)
                    count += 1
            return count
        except (json.JSONDecodeError, KeyError):
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        tools = list(self.tools.values())
        enabled = [t for t in tools if t.enabled]
        total_calls = sum(t.call_count for t in tools)
        total_errors = sum(t.error_count for t in tools)
        return {
            "total": len(tools),
            "enabled": len(enabled),
            "disabled": len(tools) - len(enabled),
            "total_calls": total_calls,
            "total_errors": total_errors,
            "categories": self.list_categories(),
            "most_used": sorted(
                [{"name": t.name, "calls": t.call_count} for t in tools],
                key=lambda x: x["calls"],
                reverse=True,
            )[:5],
        }
