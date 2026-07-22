"""MCP (Model Context Protocol) client integration for Xeno.

Enables dynamic tool loading from MCP servers, following the deepagents guide's
first-class MCP support pattern. Supports stdio and SSE transports.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from xeno.metadata import CapabilityIndex, ComponentMetadata, load_mcp_metadata

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: Optional[str] = None
    args: list[str] = field(default_factory=list)
    url: Optional[str] = None  # For SSE transport
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # "stdio" or "sse"
    enabled: bool = True


@dataclass
class MCPTool:
    """Represents a tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    server_url: Optional[str] = None


class MCPClientManager:
    """Manages connections to MCP servers and tool discovery.

    Supports both stdio and SSE transports. Discovers tools automatically
    and provides a unified interface for tool execution.
    Loads metadata.json from server directories for capability-based matching.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("data/mcp.json")
        self.servers: dict[str, MCPServerConfig] = {}
        self.tools: dict[str, MCPTool] = {}
        self._connections: dict[str, Any] = {}
        self._initialized = False
        self._capability_index = CapabilityIndex()
        self._server_metadata: dict[str, ComponentMetadata] = {}

    @property
    def capability_index(self) -> CapabilityIndex:
        return self._capability_index

    def load_config(self) -> None:
        """Load MCP server configurations from file."""
        if not self.config_path.exists():
            self._save_default_config()
            return

        try:
            data = json.loads(self.config_path.read_text())
            for name, server_data in data.get("mcpServers", {}).items():
                self.servers[name] = MCPServerConfig(
                    name=name,
                    command=server_data.get("command"),
                    args=server_data.get("args", []),
                    url=server_data.get("url"),
                    env=server_data.get("env", {}),
                    transport=server_data.get("transport", "stdio"),
                    enabled=server_data.get("enabled", True),
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load MCP config: {e}")

    def _save_default_config(self) -> None:
        """Create a default MCP configuration file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        default = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                    "transport": "stdio",
                    "enabled": False,
                },
                "web-search": {
                    "url": "http://localhost:3001/sse",
                    "transport": "sse",
                    "enabled": False,
                },
            }
        }
        self.config_path.write_text(json.dumps(default, indent=2))
        logger.info(f"Created default MCP config at {self.config_path}")

    def add_server(self, config: MCPServerConfig) -> None:
        """Add a server configuration at runtime."""
        self.servers[config.name] = config

    def load_server_metadata(self, server_dirs: list[Path]) -> int:
        """Load metadata.json from MCP server directories.
        Returns the number of servers registered with the capability index."""
        count = 0
        for server_dir in server_dirs:
            meta = load_mcp_metadata(server_dir)
            if meta:
                self._server_metadata[meta.name] = meta
                self._capability_index.register(meta)
                count += 1
                logger.info(f"Loaded MCP metadata: {meta.name}")
        return count

    def search_servers(self, query: str, top_k: int = 5) -> list[ComponentMetadata]:
        """Search for MCP servers matching a natural language query."""
        return self._capability_index.search(query, top_k=top_k, component_type="mcp")

    async def connect_server(self, name: str) -> bool:
        """Connect to an MCP server."""
        if name not in self.servers:
            logger.error(f"MCP server '{name}' not configured")
            return False

        config = self.servers[name]
        if not config.enabled:
            logger.info(f"MCP server '{name}' is disabled, skipping")
            return False

        try:
            if config.transport == "stdio":
                return await self._connect_stdio(config)
            elif config.transport == "sse":
                return await self._connect_sse(config)
            else:
                logger.error(f"Unknown transport: {config.transport}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            return False

    async def _connect_stdio(self, config: MCPServerConfig) -> bool:
        """Connect to a stdio MCP server."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env if config.env else None,
            )
            transport = await stdio_client(params).__aenter__()
            session = ClientSession(transport[0], transport[1])
            await session.__aenter__()
            await session.initialize()

            self._connections[config.name] = {"session": session, "transport": transport}
            await self._discover_tools(config.name, session)
            logger.info(f"Connected to MCP server '{config.name}' (stdio)")
            return True
        except ImportError:
            logger.warning("mcp package not installed. Install with: pip install mcp")
            return False

    async def _connect_sse(self, config: MCPServerConfig) -> bool:
        """Connect to an SSE MCP server."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            transport = await sse_client(config.url).__aenter__()
            session = ClientSession(transport[0], transport[1])
            await session.__aenter__()
            await session.initialize()

            self._connections[config.name] = {"session": session, "transport": transport}
            await self._discover_tools(config.name, session)
            logger.info(f"Connected to MCP server '{config.name}' (SSE)")
            return True
        except ImportError:
            logger.warning("mcp package not installed. Install with: pip install mcp")
            return False

    async def _discover_tools(self, server_name: str, session: Any) -> None:
        """Discover tools from an MCP server."""
        try:
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                mcp_tool = MCPTool(
                    name=f"{server_name}_{tool.name}",
                    description=tool.description or f"Tool from {server_name}",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=server_name,
                )
                self.tools[mcp_tool.name] = mcp_tool
                logger.info(f"Discovered tool: {mcp_tool.name}")
        except Exception as e:
            logger.error(f"Failed to discover tools from '{server_name}': {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool by name."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        tool = self.tools[tool_name]
        if tool.server_name not in self._connections:
            raise ConnectionError(f"MCP server '{tool.server_name}' not connected")

        conn = self._connections[tool.server_name]
        session = conn["session"]

        # Get the original tool name (strip server prefix)
        original_name = tool_name[len(tool.server_name) + 1:]

        try:
            result = await session.call_tool(original_name, arguments)
            return result
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            raise

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for name, conn in self._connections.items():
            try:
                await conn["session"].__aexit__(None, None, None)
                await conn["transport"].__aexit__(None, None, None)
                logger.info(f"Disconnected from MCP server '{name}'")
            except Exception as e:
                logger.warning(f"Error disconnecting from '{name}': {e}")
        self._connections.clear()

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in LangChain format for agent binding."""
        definitions = []
        for tool in self.tools.values():
            definitions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            })
        return definitions

    def list_servers(self) -> dict[str, str]:
        """List all configured servers and their status."""
        status = {}
        for name, config in self.servers.items():
            if name in self._connections:
                status[name] = "connected"
            elif config.enabled:
                status[name] = "enabled (not connected)"
            else:
                status[name] = "disabled"
        return status

    def list_tools(self) -> list[dict[str, str]]:
        """List all discovered tools."""
        return [
            {"name": t.name, "description": t.description, "server": t.server_name}
            for t in self.tools.values()
        ]


# ============================================================================
# Singleton getter
# ============================================================================

_mcp_manager_instance = None


def get_mcp_manager():
    """Get or create the global MCP client manager singleton."""
    global _mcp_manager_instance
    if _mcp_manager_instance is None:
        try:
            _mcp_manager_instance = MCPClientManager()
            _mcp_manager_instance.load_config()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to create MCP manager: {e}")
            return None
    return _mcp_manager_instance
