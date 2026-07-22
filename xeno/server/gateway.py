"""Gateway API — unified agent management, health checks, routing, and versioning.

Inspired by OpenClaw's Gateway architecture:
- Central registry of all agents (local + discovered)
- Health checks with configurable intervals
- Smart routing: pick the best agent for a task
- Version tracking for agents and their capabilities
- Rate limiting per endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AgentHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class RouteStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    FASTEST = "fastest"
    PREFERRED = "preferred"


@dataclass
class GatewayAgentRecord:
    id: str
    name: str
    type: str  # local, remote_mcp, remote_a2a, remote_agntcy
    url: str = ""
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    health: AgentHealth = AgentHealth.UNKNOWN
    last_health_check: float = 0.0
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    avg_response_ms: float = 0.0
    registered_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.health, str):
            try:
                self.health = AgentHealth(self.health)
            except ValueError:
                self.health = AgentHealth.UNKNOWN

    def to_dict(self) -> dict:
        d = asdict(self)
        d["health"] = self.health.value if isinstance(self.health, AgentHealth) else self.health
        return d

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests


class GatewayAPI:
    """Central gateway for managing and routing to all agents."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/gateway")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._agents: dict[str, GatewayAgentRecord] = {}
        self._route_strategy = RouteStrategy.ROUND_ROBIN
        self._rr_index: dict[str, int] = defaultdict(int)
        self._health_task: Optional[asyncio.Task] = None
        self._running = False
        self._load()

    def _load(self):
        p = self.data_dir / "agents.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for item in data:
                    rec = GatewayAgentRecord(**item)
                    self._agents[rec.id] = rec
            except Exception as e:
                logger.warning(f"Failed to load gateway agents: {e}")

    def _save(self):
        p = self.data_dir / "agents.json"
        try:
            p.write_text(
                json.dumps([a.to_dict() for a in self._agents.values()], indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save gateway agents: {e}")

    def register_agent(self, name: str, agent_type: str, **kwargs) -> str:
        aid = kwargs.pop("id", f"ga_{uuid.uuid4().hex[:8]}")
        rec = GatewayAgentRecord(
            id=aid,
            name=name,
            type=agent_type,
            url=kwargs.pop("url", ""),
            version=kwargs.pop("version", "1.0.0"),
            description=kwargs.pop("description", ""),
            capabilities=kwargs.pop("capabilities", []),
            tools=kwargs.pop("tools", []),
            tags=kwargs.pop("tags", []),
            metadata=kwargs,
        )
        self._agents[aid] = rec
        self._save()
        logger.info(f"Gateway registered agent: {name} ({aid}, type={agent_type})")
        return aid

    def unregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._save()
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[GatewayAgentRecord]:
        return self._agents.get(agent_id)

    def list_agents(self, health: Optional[AgentHealth] = None, type_filter: Optional[str] = None) -> list:
        results = list(self._agents.values())
        if health:
            results = [a for a in results if a.health == health]
        if type_filter:
            results = [a for a in results if a.type == type_filter]
        return results

    def record_request(self, agent_id: str, success: bool, duration_ms: float):
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.total_requests += 1
        if success:
            agent.successful_requests += 1
        ms = agent.avg_response_ms
        agent.avg_response_ms = (ms * (agent.total_requests - 1) + duration_ms) / agent.total_requests if agent.total_requests > 0 else duration_ms
        self._save()

    def set_health(self, agent_id: str, health: AgentHealth):
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.health = health
        agent.last_health_check = time.time()
        if health in (AgentHealth.HEALTHY,):
            agent.consecutive_failures = 0
        elif health in (AgentHealth.UNHEALTHY, AgentHealth.DEGRADED):
            agent.consecutive_failures += 1
        self._save()

    def set_strategy(self, strategy: RouteStrategy):
        self._route_strategy = strategy

    def route(self, required_capability: str = "", preferred_agent: str = "") -> Optional[GatewayAgentRecord]:
        candidates = [a for a in self._agents.values() if a.health in (AgentHealth.HEALTHY, AgentHealth.DEGRADED)]
        if preferred_agent and preferred_agent in self._agents:
            pref = self._agents[preferred_agent]
            if pref.health in (AgentHealth.HEALTHY, AgentHealth.DEGRADED):
                return pref
        if required_capability:
            candidates = [a for a in candidates if required_capability in a.capabilities]
        if not candidates:
            return None
        if self._route_strategy == RouteStrategy.ROUND_ROBIN:
            idx = self._rr_index["_global"] % len(candidates)
            self._rr_index["_global"] += 1
            return candidates[idx]
        elif self._route_strategy == RouteStrategy.LEAST_BUSY:
            return min(candidates, key=lambda a: a.total_requests - a.successful_requests)
        elif self._route_strategy == RouteStrategy.FASTEST:
            return min(candidates, key=lambda a: a.avg_response_ms if a.avg_response_ms > 0 else 999999)
        elif self._route_strategy == RouteStrategy.PREFERRED:
            healthy = [a for a in candidates if a.health == AgentHealth.HEALTHY]
            return max(healthy or candidates, key=lambda a: a.success_rate)
        return candidates[0] if candidates else None

    async def health_check_all(self, check_fn: Optional[Callable[[str], Awaitable[bool]]] = None):
        for agent in self._agents.values():
            if check_fn:
                try:
                    ok = await check_fn(agent.url or agent.id)
                    self.set_health(agent.id, AgentHealth.HEALTHY if ok else AgentHealth.UNHEALTHY)
                except Exception:
                    self.set_health(agent.id, AgentHealth.UNHEALTHY)
            else:
                self.set_health(agent.id, AgentHealth.HEALTHY)

    async def start_health_loop(self, interval: float = 30.0, check_fn: Optional[Callable[[str], Awaitable[bool]]] = None):
        if self._running:
            return
        self._running = True
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self.health_check_all(check_fn)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._health_task:
            self._health_task.cancel()

    def stats(self) -> dict:
        return {
            "total_agents": len(self._agents),
            "healthy": len([a for a in self._agents.values() if a.health == AgentHealth.HEALTHY]),
            "unhealthy": len([a for a in self._agents.values() if a.health == AgentHealth.UNHEALTHY]),
            "strategy": self._route_strategy.value,
        }



