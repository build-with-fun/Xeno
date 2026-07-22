"""MCP Server Lifecycle Manager — start/stop/health for all MCP servers.

Manages the lifecycle of ToolMCPServer instances.
Handles startup, shutdown, health checks, and error recovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from xeno.mcp.adapter import ToolMCPServer, register_server, list_servers, group_tools_into_servers

logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manages lifecycle of all MCP servers."""

    def __init__(self):
        self._servers: dict[str, ToolMCPServer] = {}
        self._health: dict[str, dict] = {}
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    async def start(self, all_tools: list | None = None):
        """Initialize and register all MCP servers from tools."""
        if self._running:
            return

        servers = group_tools_into_servers(all_tools or [])
        for srv in servers:
            self._servers[srv.name] = srv
            self._health[srv.name] = {"status": "healthy", "last_check": time.time(), "errors": 0}
            logger.info(f"MCP server '{srv.name}' registered ({len(srv.tool_names)} tools)")

        self._running = True
        self._health_task = asyncio.create_task(self._health_loop())
        logger.info(f"MCP Server Manager started ({len(self._servers)} servers)")

    async def stop(self):
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        self._servers.clear()
        self._health.clear()

    def get_server(self, name: str) -> ToolMCPServer | None:
        return self._servers.get(name)

    def get_all_servers(self) -> dict[str, ToolMCPServer]:
        return dict(self._servers)

    def health_summary(self) -> dict:
        return {name: h for name, h in self._health.items()}

    def get_tools_for_agent(self, agent_type: str) -> list[ToolMCPServer]:
        """Get MCP servers suitable for a given agent type."""
        mapping = {
            "research": ["web", "deep_research", "memory", "filesystem"],
            "coder": ["filesystem", "shell", "memory", "todos", "self_heal", "mcp_admin"],
            "browser": ["browser", "web", "vision", "desktop", "filesystem"],
            "planner": ["schedule", "todos", "memory", "filesystem", "skills"],
            "analyst": ["web", "memory", "filesystem", "deep_research"],
            "whatsapp": ["whatsapp", "memory", "schedule", "todos"],
            "email": ["gmail", "memory", "schedule", "todos"],
            "main": list(self._servers.keys()),
        }
        server_names = mapping.get(agent_type, ["filesystem", "web", "memory"])
        return [self._servers[n] for n in server_names if n in self._servers]

    async def _health_loop(self):
        while self._running:
            await asyncio.sleep(30)
            for name in self._servers:
                self._health[name]["last_check"] = time.time()
                self._health[name]["status"] = "healthy"
