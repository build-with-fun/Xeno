"""Always-On Agent Base — dual-mode agents with MCP server + standalone capability.

Each always-on agent has:
- Mode A: MCP server controlled by the Main Agent
- Mode B: Standalone agent instance with own tools/MCP servers
- Temporal KG memory (namespace per agent)
- Duration tracking (auto-expire after N hours/days)
- Scheduler integration for recurring iterations
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from xeno.memory.temporal import get_temporal_kg, TemporalKnowledgeGraph
from xeno.mcp.adapter import ToolMCPServer, register_server

logger = logging.getLogger(__name__)


class AgentMode(Enum):
    MCP_SERVER = "mcp_server"       # Main Agent orchestrates via MCP
    STANDALONE = "standalone"       # Independent agent instance
    DUAL = "dual"                   # Both modes simultaneously


class AgentState(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Configuration for an always-on agent."""
    name: str
    provider_type: str  # "whatsapp", "email", etc.
    mode: AgentMode = AgentMode.DUAL
    duration_hours: float = 0  # 0 = indefinite
    schedule_interval_seconds: float = 300  # check interval
    model: str = ""
    tools: list = field(default_factory=list)
    mcp_servers: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AlwaysOnAgent(ABC):
    """Base class for always-on agents with dual-mode capability."""

    def __init__(self, config: AgentConfig, data_dir: Optional[Path] = None):
        self.config = config
        self.state = AgentState.CREATED
        self.started_at: Optional[float] = None
        self.state_changed_at: float = time.time()
        self.agent_id = f"{config.name}_{uuid.uuid4().hex[:6]}"

        data_path = data_dir or Path("data/always_on")
        self._state_dir = data_path / config.name
        self._state_dir.mkdir(parents=True, exist_ok=True)

        self._temporal_kg = get_temporal_kg(f"always_on_{config.name}",
                                            storage_path=self._state_dir)
        self._iteration_task: Optional[asyncio.Task] = None

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        if not self.started_at or self.config.duration_hours <= 0:
            return False
        return (time.time() - self.started_at) > (self.config.duration_hours * 3600)

    @property
    def elapsed_hours(self) -> float:
        if not self.started_at:
            return 0
        return (time.time() - self.started_at) / 3600

    @property
    def remaining_hours(self) -> float:
        if not self.started_at or self.config.duration_hours <= 0:
            return float("inf")
        return max(0, self.config.duration_hours - self.elapsed_hours)

    # ── Core Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        """Start the agent. Sets up MCP server and/or standalone loop."""
        if self.state == AgentState.RUNNING:
            return
        self.state = AgentState.RUNNING
        self.started_at = time.time()
        self.state_changed_at = time.time()

        if self.config.mode in (AgentMode.MCP_SERVER, AgentMode.DUAL):
            await self._setup_mcp_server()

        if self.config.mode in (AgentMode.STANDALONE, AgentMode.DUAL):
            self._iteration_task = asyncio.create_task(self._iteration_loop())

        logger.info(f"Always-on agent '{self.config.name}' started (mode={self.config.mode.value})")

    async def stop(self):
        """Stop the agent."""
        if self._iteration_task:
            self._iteration_task.cancel()
            try:
                await self._iteration_task
            except asyncio.CancelledError:
                pass
            self._iteration_task = None
        self.state = AgentState.PAUSED
        self.state_changed_at = time.time()
        await self._cleanup()
        logger.info(f"Always-on agent '{self.config.name}' stopped")

    async def pause(self):
        if self._iteration_task:
            self._iteration_task.cancel()
            self._iteration_task = None
        self.state = AgentState.PAUSED
        self.state_changed_at = time.time()

    async def resume(self):
        await self.start()

    async def expire(self):
        self.state = AgentState.EXPIRED
        self.state_changed_at = time.time()
        await self.stop()

    # ── MCP Server Mode ───────────────────────────────────────────────────

    async def _setup_mcp_server(self):
        """Register this agent as an MCP server the Main Agent can call."""
        srv = ToolMCPServer(self.config.name, [
            self._mcp_handle_event,
            self._mcp_get_status,
            self._mcp_get_memory_context,
        ])
        register_server(srv)
        self._mcp_server = srv

    async def _mcp_handle_event(self, event_type: str, data_json: str = "{}") -> str:
        """MCP tool: handle an incoming event (message, notification, etc.)."""
        import json
        data = json.loads(data_json)
        return await self.handle_event(event_type, data)

    async def _mcp_get_status(self) -> str:
        """MCP tool: get agent status."""
        status = self.get_status()
        import json
        return json.dumps(status, default=str)

    async def _mcp_get_memory_context(self) -> str:
        """MCP tool: get memory context for Main Agent."""
        return self._temporal_kg.export_context()

    # ── Standalone Mode ───────────────────────────────────────────────────

    async def _iteration_loop(self):
        """Background loop that periodically runs iterations."""
        while True:
            try:
                await asyncio.sleep(self.config.schedule_interval_seconds)
                if self.state != AgentState.RUNNING:
                    break
                if self.is_expired:
                    await self.expire()
                    break
                await self.run_iteration()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Always-on agent '{self.config.name}' iteration error: {e}")

    # ── Abstract Methods (implemented by subclasses) ──────────────────────

    @abstractmethod
    async def handle_event(self, event_type: str, data: dict) -> str:
        """Handle an incoming event (message, notification, etc.)."""
        ...

    @abstractmethod
    async def run_iteration(self) -> dict:
        """Run a single iteration (check for messages, process, etc.). Returns results."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the provider service."""
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the provider service."""
        ...

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.config.name,
            "state": self.state.value,
            "mode": self.config.mode.value,
            "elapsed_hours": self.elapsed_hours,
            "remaining_hours": self.remaining_hours if self.config.duration_hours > 0 else None,
            "is_expired": self.is_expired,
            "memory_facts": len(self._temporal_kg.facts),
            "started_at": self.started_at,
        }

    async def _cleanup(self):
        """Cleanup resources."""
        pass
