"""Always-On Agent Manager — lifecycle, auto-resume, state persistence.

Handles:
- Starting/stopping all always-on agents
- Auto-resume on startup (loads last active agents)
- State persistence (which agents were running, their durations)
- Coordination with scheduler
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from xeno.always_on.base import AlwaysOnAgent, AgentConfig, AgentMode, AgentState
from xeno.config import XenoConfig

logger = logging.getLogger(__name__)


class AlwaysOnManager:
    """Manages lifecycle of all always-on agents."""

    def __init__(self, config: Optional[XenoConfig] = None):
        self.config = config or XenoConfig.from_env()
        self._agents: dict[str, AlwaysOnAgent] = {}
        self._state_file = self.config.data_dir / "always_on" / "manager_state.json"
        self._auto_resume = True
        self._loaded = False

    def register(self, agent: AlwaysOnAgent):
        """Register an always-on agent."""
        self._agents[agent.config.name] = agent
        logger.info(f"Always-on agent '{agent.config.name}' registered")

    def get(self, name: str) -> Optional[AlwaysOnAgent]:
        return self._agents.get(name)

    def list_agents(self) -> list[dict]:
        return [a.get_status() for a in self._agents.values()]

    def get_active(self) -> list[AlwaysOnAgent]:
        return [a for a in self._agents.values() if a.state == AgentState.RUNNING]

    async def start_all(self):
        """Start all registered agents."""
        for name, agent in self._agents.items():
            try:
                await agent.start()
            except Exception as e:
                logger.warning(f"Failed to start agent '{name}': {e}")

        if self._auto_resume:
            await self._resume_from_state()

        self._loaded = True
        logger.info(f"Always-on manager: {len(self._agents)} agents registered")

    async def stop_all(self):
        """Stop all agents."""
        for name, agent in self._agents.items():
            try:
                await agent.stop()
            except Exception:
                pass
        self._save_state()
        logger.info("All always-on agents stopped")

    async def start_agent(self, name: str) -> str:
        agent = self._agents.get(name)
        if not agent:
            return f"Agent '{name}' not found"
        await agent.start()
        return f"Agent '{name}' started"

    async def stop_agent(self, name: str) -> str:
        agent = self._agents.get(name)
        if not agent:
            return f"Agent '{name}' not found"
        await agent.stop()
        return f"Agent '{name}' stopped"

    async def pause_agent(self, name: str) -> str:
        agent = self._agents.get(name)
        if not agent:
            return f"Agent '{name}' not found"
        await agent.pause()
        return f"Agent '{name}' paused"

    async def resume_agent(self, name: str) -> str:
        agent = self._agents.get(name)
        if not agent:
            return f"Agent '{name}' not found"
        await agent.resume()
        return f"Agent '{name}' resumed"

    def get_status(self) -> dict:
        return {
            "total": len(self._agents),
            "active": len(self.get_active()),
            "agents": self.list_agents(),
        }

    def _save_state(self):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {}
        for name, agent in self._agents.items():
            if agent.state in (AgentState.RUNNING, AgentState.PAUSED):
                state[name] = {
                    "mode": agent.config.mode.value,
                    "started_at": agent.started_at,
                    "duration_hours": agent.config.duration_hours,
                }
        self._state_file.write_text(json.dumps(state, indent=2))

    async def _resume_from_state(self):
        if not self._state_file.exists():
            return
        try:
            state = json.loads(self._state_file.read_text())
            for name, saved in state.items():
                agent = self._agents.get(name)
                if agent and agent.state != AgentState.RUNNING:
                    remaining = saved.get("duration_hours", 0)
                    elapsed = (time.time() - saved.get("started_at", time.time())) / 3600
                    if remaining > 0 and elapsed >= remaining:
                        logger.info(f"Agent '{name}' already expired (elapsed={elapsed:.1f}h)")
                        continue
                    await agent.start()
                    logger.info(f"Auto-resumed agent '{name}'")
        except Exception as e:
            logger.warning(f"Auto-resume failed: {e}")

    async def cleanup_expired(self):
        """Stop and remove expired agents."""
        for name, agent in list(self._agents.items()):
            if agent.is_expired:
                await agent.expire()
                logger.info(f"Agent '{name}' expired and stopped")


_manager_instance: Optional[AlwaysOnManager] = None


def get_always_on_manager() -> AlwaysOnManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AlwaysOnManager()
    return _manager_instance
