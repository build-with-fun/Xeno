"""MCP 2025 client — real stdio/SSE connections using the official mcp library."""

from __future__ import annotations
import asyncio, json, logging, time, uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

class MCPServerType(str, Enum):
    LOCAL_STDIO = "local"
    REMOTE_SSE = "remote_sse"
    REMOTE_HTTP = "remote_http"

class MCPAuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    BEARER = "bearer"

@dataclass
class MCPServerCard:
    name: str
    version: str
    description: str = ""
    tools: list = field(default_factory=list)
    auth: MCPAuthType = MCPAuthType.NONE
    capabilities: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class MCPToolInfo:
    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)

@dataclass
class MCPAsyncTask:
    id: str
    server: str
    tool: str
    args: dict
    status: str = "pending"
    progress: float = 0.0
    result: Any = None
    error: str = ""

class MCPSession:
    def __init__(self, server_name: str, server_type: MCPServerType, config: dict):
        self.server_name = server_name
        self.server_type = server_type
        self.config = config
        self._session = None
        self._transport = None
        self._tools: list[MCPToolInfo] = []
        self._capabilities: dict = {}

    async def connect(self) -> bool:
        try:
            from mcp.client.session import ClientSession as MCPSessionClient
            if self.server_type == MCPServerType.LOCAL_STDIO:
                from mcp.client.stdio import stdio_client, StdioServerParameters
                cmd = self.config.get("command", [])
                env = self.config.get("env", {})
                params = StdioServerParameters(
                    command=cmd[0] if cmd else "python",
                    args=cmd[1:] if len(cmd) > 1 else [],
                    env={**env} if env else None,
                )
                self._transport = await stdio_client(params).__aenter__()
                read, write = self._transport
                self._session = await MCPSessionClient(read, write).__aenter__()
            elif self.server_type == MCPServerType.REMOTE_SSE:
                from mcp.client.sse import sse_client
                url = self.config.get("url", "")
                if not url:
                    raise ValueError("SSE server requires a url")
                self._transport = await sse_client(url=url).__aenter__()
                read, write = self._transport
                self._session = await MCPSessionClient(read, write).__aenter__()
            elif self.server_type == MCPServerType.REMOTE_HTTP:
                from mcp.client.streamable_http import streamable_http_client
                url = self.config.get("url", "")
                if not url:
                    raise ValueError("HTTP server requires a url")
                from mcp.types import InitializeRequestParams
                self._transport = await streamable_http_client(url=url, session_id="").__aenter__()
                read, write = self._transport
                self._session = await MCPSessionClient(read, write).__aenter__()
            else:
                raise ValueError(f"Unknown server type: {self.server_type}")
            result = await self._session.initialize()
            self._capabilities = result.capabilities.model_dump() if hasattr(result.capabilities, "model_dump") else {}
            logger.info(f"MCP server '{self.server_name}' connected (type={self.server_type.value})")
            return True
        except Exception as e:
            logger.warning(f"MCP server '{self.server_name}' connect failed: {e}")
            return False

    async def list_tools(self) -> list[MCPToolInfo]:
        if not self._session:
            return []
        try:
            result = await self._session.list_tools()
            self._tools = [
                MCPToolInfo(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema if hasattr(t, "inputSchema") else {},
                )
                for t in result.tools
            ]
            return self._tools
        except Exception as e:
            logger.warning(f"list_tools failed for '{self.server_name}': {e}")
            return []

    async def call_tool(self, tool_name: str, args: dict) -> Any:
        if not self._session:
            raise RuntimeError(f"MCP server '{self.server_name}' not connected")
        try:
            result = await self._session.call_tool(tool_name, arguments=args)
            content = result.content if hasattr(result, "content") else result
            texts = []
            for c in (content or []):
                if hasattr(c, "text"):
                    texts.append(c.text)
                elif isinstance(c, dict):
                    texts.append(c.get("text", str(c)))
                else:
                    texts.append(str(c))
            return "\n".join(texts)
        except Exception as e:
            raise RuntimeError(f"MCP tool '{tool_name}' on '{self.server_name}' failed: {e}")

    async def disconnect(self):
        try:
            if self._session:
                await self._session.__aexit__(None, None, None)
            if self._transport:
                await self._transport.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Disconnect '{self.server_name}': {e}")
        self._session = None
        self._transport = None

    @property
    def connected(self) -> bool:
        return self._session is not None

    @property
    def tools(self) -> list[MCPToolInfo]:
        return self._tools

class MCP2025Client:
    def __init__(self, base_client=None, oauth_callback=None, elicitation_callback=None):
        self.base = base_client
        self._servers: dict[str, MCPServerCard] = {}
        self._sessions: dict[str, MCPSession] = {}
        self._config_path: Optional[Path] = None

    def load_config(self, config_path: Path):
        self._config_path = config_path
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                for name, cfg in data.items():
                    server_type_str = cfg.get("type", "local")
                    try:
                        st = MCPServerType(server_type_str)
                    except ValueError:
                        st = MCPServerType.LOCAL_STDIO
                    card = MCPServerCard(
                        name=name,
                        version=cfg.get("version", "1.0.0"),
                        description=cfg.get("description", ""),
                        auth=MCPAuthType(cfg.get("auth", "none")) if cfg.get("auth") else MCPAuthType.NONE,
                    )
                    self._servers[name] = card
                    self._sessions[name] = MCPSession(name, st, cfg)
                logger.info(f"Loaded {len(data)} MCP servers from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load MCP config from {config_path}: {e}")

    async def connect_all(self) -> dict[str, bool]:
        results = {}
        for name, session in self._sessions.items():
            results[name] = await session.connect()
            if results[name]:
                tools = await session.list_tools()
                if name in self._servers:
                    self._servers[name].tools = [t.name for t in tools]
        return results

    async def connect_server(self, name: str) -> bool:
        session = self._sessions.get(name)
        if not session:
            return False
        ok = await session.connect()
        if ok:
            tools = await session.list_tools()
            if name in self._servers:
                self._servers[name].tools = [t.name for t in tools]
        return ok

    async def fetch_server_card(self, name: str) -> Optional[MCPServerCard]:
        session = self._sessions.get(name)
        if not session:
            return self._servers.get(name)
        if not session.connected:
            ok = await session.connect()
            if ok:
                await session.list_tools()
        card = self._servers.get(name)
        if card and session:
            card.tools = [t.name for t in session.tools]
        return card

    async def call_tool_server(self, server_name: str, tool_name: str, args: dict = None) -> Any:
        session = self._sessions.get(server_name)
        if not session:
            raise RuntimeError(f"Unknown MCP server: {server_name}")
        if not session.connected:
            ok = await session.connect()
            if not ok:
                raise RuntimeError(f"Cannot connect to MCP server: {server_name}")
        return await session.call_tool(tool_name, args or {})

    def list_servers(self) -> list:
        return list(self._servers.values())

    def list_connected(self) -> list[str]:
        return [n for n, s in self._sessions.items() if s.connected]

    def get_tools_flat(self) -> list[dict]:
        flat = []
        for name, session in self._sessions.items():
            for tool in session.tools:
                flat.append({
                    "server": name,
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                })
        return flat

    async def add_server(self, name: str, server_type: str, **config) -> bool:
        try:
            st = MCPServerType(server_type)
        except ValueError:
            st = MCPServerType.LOCAL_STDIO
        card = MCPServerCard(name=name, version="1.0.0", description=config.get("description", ""))
        self._servers[name] = card
        self._sessions[name] = MCPSession(name, st, config)
        if self._config_path:
            try:
                data = {}
                if self._config_path.exists():
                    data = json.loads(self._config_path.read_text(encoding="utf-8"))
                data[name] = {"type": server_type, **config}
                self._config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to save MCP config: {e}")
        return True

    async def remove_server(self, name: str) -> bool:
        session = self._sessions.pop(name, None)
        if session:
            await session.disconnect()
        self._servers.pop(name, None)
        if self._config_path:
            try:
                data = {}
                if self._config_path.exists():
                    data = json.loads(self._config_path.read_text(encoding="utf-8"))
                data.pop(name, None)
                self._config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to update MCP config: {e}")
        return True

    async def disconnect_all(self):
        for session in self._sessions.values():
            await session.disconnect()
        self._sessions.clear()

    async def disconnect(self, name: str):
        session = self._sessions.get(name)
        if session:
            await session.disconnect()
