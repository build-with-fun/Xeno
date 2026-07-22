"""24/7 Always-On Agent Manager — Fully Dynamic.

Manages long-running agent processes that run continuously.
Any agent in agents/ with always_on: true is auto-discovered and started.

Features:
- Start/stop/restart any agent
- Health monitoring with heartbeat
- Auto-restart on failure (with backoff)
- State persistence across restarts
- Custom tools per agent (from agents/<name>/tools/)
- Real LLM execution with agent's model, tools, prompt
- Any agent can control other agents
- Dynamic CRUD via REST API
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    RESTARTING = "restarting"


class RestartPolicy(str, Enum):
    NEVER = "never"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"
    WITH_BACKOFF = "with_backoff"


@dataclass
class AgentConfig:
    """Configuration for a 24/7 agent."""
    name: str
    description: str = ""
    prompt: str = ""
    agent_type: str = "generic"
    enabled: bool = True
    restart_policy: str = "with_backoff"
    max_restarts: int = 10
    restart_delay_seconds: int = 30
    heartbeat_interval_seconds: int = 60
    check_interval_minutes: int = 5
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    custom_tools: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    schedule: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_descriptor_id: str = ""


@dataclass
class AgentStatus:
    """Runtime status of a 24/7 agent."""
    state: str = "stopped"
    started_at: str | None = None
    last_heartbeat: str | None = None
    last_task_run: str | None = None
    restart_count: int = 0
    last_error: str | None = None
    tasks_completed: int = 0
    errors_count: int = 0
    pid: int | None = None
    uptime_seconds: float = 0.0


@dataclass
class RunningAgent:
    """A running 24/7 agent with its config and status."""
    config: AgentConfig
    status: AgentStatus
    _task: asyncio.Task | None = field(default=None, repr=False)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _llm: Any = field(default=None, repr=False)
    _custom_tool_funcs: list = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        return {
            "config": asdict(self.config),
            "status": asdict(self.status),
            "custom_tools_loaded": len(self._custom_tool_funcs),
        }


class AlwaysOnManager:
    """Manages all 24/7 always-on agents — fully dynamic from discovery system.

    Agents are created from AgentDescriptor objects (discovered from description.md).
    Each agent gets its own LLM instance, tools, and system prompt.
    Custom tools are loaded from agents/<name>/tools/ directories.
    """

    def __init__(self, data_dir: Path, config: Any = None):
        self.data_dir = data_dir
        self.config = config  # Main XenoConfig for API keys / provider resolution
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.agents_file = data_dir / "always_on_agents.json"
        self._agents: dict[str, RunningAgent] = {}
        self._callbacks: dict[str, Callable] = {}
        self._loaded = False
        self._agent_executor: Callable | None = None

    def set_agent_executor(self, executor: Callable) -> None:
        """Set the function that creates an LLM agent from config.

        executor(model, tools, system_prompt, temperature, max_tokens) -> agent
        """
        self._agent_executor = executor

    async def initialize(self) -> None:
        """Load persisted agent configs and start enabled ones."""
        if self._loaded:
            return
        self._load_configs()
        self._loaded = True
        for agent_id, agent in self._agents.items():
            if agent.config.enabled:
                logger.info(f"Auto-starting 24/7 agent: {agent.config.name}")
                await self.start_agent(agent_id)

    def _load_configs(self) -> None:
        """Load agent configs from disk."""
        if not self.agents_file.exists():
            return
        try:
            data = json.loads(self.agents_file.read_text(encoding="utf-8"))
            for agent_id, agent_data in data.items():
                config = AgentConfig(**agent_data.get("config", {}))
                status = AgentStatus(**agent_data.get("status", {"state": "stopped"}))
                self._agents[agent_id] = RunningAgent(config=config, status=status)
        except Exception as e:
            logger.error(f"Failed to load always-on agent configs: {e}")

    def _save_configs(self) -> None:
        """Persist agent configs to disk."""
        data = {}
        for agent_id, agent in self._agents.items():
            data[agent_id] = {
                "config": asdict(agent.config),
                "status": {"state": "stopped"},
            }
        self.agents_file.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def _build_config_from_descriptor(self, descriptor: Any) -> AgentConfig:
        """Create an AgentConfig from a discovered AgentDescriptor."""
        return AgentConfig(
            name=descriptor.name,
            description=descriptor.description[:500] if descriptor.description else "",
            prompt=f"You are {descriptor.name}. {descriptor.description[:300]}",
            agent_type=descriptor.id,
            enabled=descriptor.enabled and descriptor.always_on,
            restart_policy=descriptor.restart_policy,
            max_restarts=descriptor.max_restarts,
            check_interval_minutes=descriptor.check_interval_minutes,
            model=self.config.model,
            tools=list(descriptor.tools),
            custom_tools=[str(Path(descriptor.folder_path) / descriptor.custom_tools_dir)],
            metadata={
                "tags": descriptor.tags,
                "permissions": descriptor.permissions,
                "temperature": descriptor.temperature,
                "max_tokens": descriptor.max_tokens,
                "folder_path": descriptor.folder_path,
                "source_descriptor_id": descriptor.id,
            },
            source_descriptor_id=descriptor.id,
        )

    def _load_custom_tools(self, agent: RunningAgent) -> list:
        """Load custom tools from the agent's tools/ directory."""
        custom_dirs = agent.config.custom_tools
        loaded = []
        for tools_dir_path in custom_dirs:
            tools_dir = Path(tools_dir_path)
            if not tools_dir.exists():
                continue
            for py_file in sorted(tools_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    module_name = f"xeno_alwayson_{agent.config.agent_type}_tool_{py_file.stem}"
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = mod
                        spec.loader.exec_module(mod)
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if callable(attr) and hasattr(attr, "name"):
                                loaded.append(attr)
                                logger.info(f"Loaded custom tool '{attr_name}' for agent {agent.config.name}")
                except Exception as e:
                    logger.error(f"Failed to load custom tool from {py_file}: {e}")
        agent._custom_tool_funcs = loaded
        return loaded

    def _create_llm_for_agent(self, agent: RunningAgent) -> Any:
        """Create a lightweight LLM instance for an always-on agent."""
        model = agent.config.model
        if not model:
            return None
        # Fall back to main config model if agent model requires missing API keys
        if model and self.config and "deepseek" in model and "DEEPSEEK_API_KEY" not in os.environ:
            model = self.config.model
        try:
            from xeno.client import get_llm_client
            from types import SimpleNamespace
            provider = getattr(self.config, 'provider', '') if self.config else ''
            pseudo_cfg = SimpleNamespace(
                model=model,
                provider=provider,
                api_keys=self.config.api_keys if self.config else {},
            )
            llm = get_llm_client(pseudo_cfg)
            if llm is None:
                raise RuntimeError("get_llm_client returned None")
            agent._llm = llm
            logger.info(f"Created LLM for {agent.config.name}: {model}")
            return llm
        except Exception as e:
            logger.error(f"Failed to create LLM for {agent.config.name}: {e}")
            return None

    async def start_agent(self, agent_id: str) -> str:
        """Start a 24/7 agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found"

        if agent.status.state == AgentState.RUNNING:
            return f"Agent '{agent.config.name}' is already running"

        agent.status.state = AgentState.STARTING
        agent.status.started_at = datetime.now().isoformat()
        agent.status.pid = os.getpid()
        agent._cancel_event.clear()

        # Load custom tools
        self._load_custom_tools(agent)

        # Create LLM if not already created
        if not agent._llm:
            self._create_llm_for_agent(agent)

        # Start the agent task
        agent._task = asyncio.create_task(
            self._run_agent_loop(agent_id),
            name=f"always_on_{agent.config.name}",
        )
        agent.status.state = AgentState.RUNNING
        self._save_configs()

        logger.info(f"Started 24/7 agent: {agent.config.name} (id: {agent_id})")
        return f"Started 24/7 agent '{agent.config.name}' (id: {agent_id})"

    async def stop_agent(self, agent_id: str) -> str:
        """Stop a 24/7 agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found"

        if agent.status.state == AgentState.STOPPED:
            return f"Agent '{agent.config.name}' is already stopped"

        agent.status.state = AgentState.STOPPING
        agent._cancel_event.set()

        if agent._task and not agent._task.done():
            agent._task.cancel()
            try:
                await asyncio.wait_for(agent._task, timeout=10)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        agent.status.state = AgentState.STOPPED
        agent.status.pid = None
        self._save_configs()

        logger.info(f"Stopped 24/7 agent: {agent.config.name}")
        return f"Stopped 24/7 agent '{agent.config.name}'"

    async def restart_agent(self, agent_id: str) -> str:
        """Restart a 24/7 agent."""
        result = await self.stop_agent(agent_id)
        if "not found" in result:
            return result
        await asyncio.sleep(2)
        return await self.start_agent(agent_id)

    async def _run_agent_loop(self, agent_id: str) -> None:
        """Main loop for a 24/7 agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return

        restart_count = 0
        max_restarts = agent.config.max_restarts

        while not agent._cancel_event.is_set():
            try:
                await self._execute_agent_task(agent_id)
                agent.status.tasks_completed += 1
                agent.status.last_heartbeat = datetime.now().isoformat()

                wait_minutes = agent.config.check_interval_minutes
                try:
                    await asyncio.wait_for(
                        agent._cancel_event.wait(),
                        timeout=wait_minutes * 60,
                    )
                    break
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                agent.status.errors_count += 1
                agent.status.last_error = str(e)
                logger.error(f"Agent '{agent.config.name}' error: {e}")

                restart_count += 1
                if restart_count > max_restarts:
                    agent.status.state = AgentState.FAILED
                    logger.error(
                        f"Agent '{agent.config.name}' exceeded max restarts ({max_restarts})"
                    )
                    break

                if agent.config.restart_policy == RestartPolicy.NEVER:
                    agent.status.state = AgentState.FAILED
                    break
                elif agent.config.restart_policy == RestartPolicy.WITH_BACKOFF:
                    delay = min(agent.config.restart_delay_seconds * (2 ** (restart_count - 1)), 3600)
                else:
                    delay = agent.config.restart_delay_seconds

                agent.status.state = AgentState.RESTARTING
                agent.status.restart_count = restart_count
                logger.info(
                    f"Agent '{agent.config.name}' restarting in {delay}s "
                    f"(attempt {restart_count}/{max_restarts})"
                )
                try:
                    await asyncio.wait_for(agent._cancel_event.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass

        agent.status.state = AgentState.STOPPED
        agent.status.pid = None
        logger.info(f"Agent '{agent.config.name}' loop ended")

    async def _execute_agent_task(self, agent_id: str) -> None:
        """Execute a single iteration of the agent's task."""
        agent = self._agents.get(agent_id)
        if not agent:
            return

        # Use the registered callback if available
        callback = self._callbacks.get(agent.config.agent_type)
        if callback:
            await callback(agent_id, agent.config)
            return

        # Use the custom LLM to run the agent's task
        await self._llm_task(agent_id, agent)

    async def _llm_task(self, agent_id: str, agent: RunningAgent) -> None:
        """Run the agent's task using its own LLM with tools."""
        llm = agent._llm
        if not llm:
            logger.warning(f"Agent '{agent.config.name}' has no LLM — skipping")
            agent.status.last_task_run = datetime.now().isoformat()
            return

        # Build the prompt
        prompt = agent.config.prompt or f"Execute your task as {agent.config.name}"
        task_prompt = (
            f"{prompt}\n\n"
            f"Current time: {datetime.now().isoformat()}\n"
            f"Check interval: every {agent.config.check_interval_minutes} minutes\n"
            f"Complete your current task. Be concise."
        )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            import platform as _plat
            messages = [
                SystemMessage(content=(
                    f"You are {agent.config.name}, a 24/7 autonomous agent.\n"
                    f"{agent.config.description}\n"
                    f"OS: {_plat.system()} {_plat.release()}\n"
                    f"Working directory: {os.getcwd()}\n"
                    f"Current time: {datetime.now().isoformat()}\n"
                    f"Be concise. Report what you did."
                )),
                HumanMessage(content=task_prompt),
            ]

            # Use custom tools if available, otherwise plain LLM
            if agent._custom_tool_funcs:
                # Create a temporary agent with custom tools
                try:
                    from deepagents import create_deep_agent
                    temp_agent = create_deep_agent(
                        model=agent.config.model or "deepseek:deepseek-chat",
                        system_prompt=messages[0].content,
                        tools=agent._custom_tool_funcs,
                    )
                    result = await asyncio.wait_for(
                        temp_agent.ainvoke({"messages": messages}),
                        timeout=120.0,
                    )
                    msgs = result.get("messages", [])
                    response = msgs[-1].content if msgs and hasattr(msgs[-1], "content") else str(result)
                except Exception as e:
                    logger.debug(f"Agent with tools failed, falling back to plain LLM: {e}")
                    result = await asyncio.wait_for(
                        llm.ainvoke(messages),
                        timeout=60.0,
                    )
                    response = result.content if hasattr(result, "content") else str(result)
            else:
                result = await asyncio.wait_for(
                    llm.ainvoke(messages),
                    timeout=60.0,
                )
                response = result.content if hasattr(result, "content") else str(result)

            agent.status.last_task_run = datetime.now().isoformat()
            logger.info(f"Agent '{agent.config.name}' task result: {response[:200]}")
            return response

        except asyncio.TimeoutError:
            logger.warning(f"Agent '{agent.config.name}' task timed out")
            agent.status.last_task_run = datetime.now().isoformat()
            return ""
        except Exception as e:
            logger.error(f"Agent '{agent.config.name}' LLM task failed: {e}")
            raise

    async def _write_context_entry(self, agent_name: str, summary: str, entry_type: str = "task_completed"):
        """Write an activity entry to the context bridge."""
        try:
            from xeno.context_bridge import AgentContextBridge
            bridge = AgentContextBridge(self.data_dir.parent / "agent_context")
            bridge.add_entry(
                agent_name=agent_name,
                entry_type=entry_type,
                summary=summary[:500],
            )
        except Exception as e:
            logger.debug(f"Context bridge write failed: {e}")

    async def _execute_agent_task(self, agent_id: str) -> None:
        """Execute a single iteration of the agent's task."""
        agent = self._agents.get(agent_id)
        if not agent:
            return

        # Use the registered callback if available
        callback = self._callbacks.get(agent.config.agent_type)
        if callback:
            await callback(agent_id, agent.config)
            await self._write_context_entry(
                agent.config.name,
                f"Completed callback cycle at {datetime.now().isoformat()[:19]}",
                "task_completed",
            )
            return

        # Use the custom LLM to run the agent's task
        response = await self._llm_task(agent_id, agent) or ""

        # Write to context bridge
        summary = response[:300].replace("\n", " ").strip() if response else f"Completed task cycle at {datetime.now().isoformat()[:19]}"
        await self._write_context_entry(agent.config.name, summary, "task_completed")

    def register_callback(self, agent_type: str, callback: Callable) -> None:
        """Register a callback for a specific agent type."""
        self._callbacks[agent_type] = callback

    def create_agent(
        self,
        name: str,
        description: str = "",
        prompt: str = "",
        agent_type: str = "generic",
        restart_policy: str = "with_backoff",
        max_restarts: int = 10,
        check_interval_minutes: int = 5,
        model: str | None = None,
        tools: list[str] | None = None,
        custom_tools_dir: str | None = None,
        env: dict[str, str] | None = None,
        schedule: dict[str, Any] | None = None,
        auto_start: bool = True,
    ) -> str:
        """Create a new 24/7 agent."""
        agent_id = str(uuid.uuid4())[:8]
        config = AgentConfig(
            name=name,
            description=description,
            prompt=prompt,
            agent_type=agent_type,
            restart_policy=restart_policy,
            max_restarts=max_restarts,
            check_interval_minutes=check_interval_minutes,
            model=model,
            tools=tools or [],
            custom_tools=[custom_tools_dir] if custom_tools_dir else [],
            env=env or {},
            schedule=schedule or {},
        )
        status = AgentStatus(state=AgentState.STOPPED)
        self._agents[agent_id] = RunningAgent(config=config, status=status)
        self._save_configs()

        logger.info(f"Created 24/7 agent '{name}' (id: {agent_id})")
        if auto_start:
            asyncio.create_task(self.start_agent(agent_id))

        return f"Created 24/7 agent '{name}' (id: {agent_id})"

    def create_agent_from_descriptor(self, descriptor: Any, auto_start: bool = True) -> str:
        """Create a 24/7 agent from a discovered AgentDescriptor."""
        # Check if already exists
        for agent in self._agents.values():
            if agent.config.source_descriptor_id == descriptor.id:
                return f"Agent '{descriptor.name}' already exists (id not shown)"

        config = self._build_config_from_descriptor(descriptor)
        status = AgentStatus(state=AgentState.STOPPED)
        agent_id = descriptor.id
        self._agents[agent_id] = RunningAgent(config=config, status=status)
        self._save_configs()

        logger.info(f"Created 24/7 agent from descriptor: {descriptor.name} (id: {agent_id})")
        return f"Created 24/7 agent '{descriptor.name}' (id: {agent_id})"

    def delete_agent(self, agent_id: str) -> str:
        """Delete a 24/7 agent (must be stopped first)."""
        agent = self._agents.get(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found"
        if agent.status.state == AgentState.RUNNING:
            return f"Cannot delete running agent. Stop it first."
        del self._agents[agent_id]
        self._save_configs()
        return f"Deleted 24/7 agent '{agent.config.name}'"

    def get_status(self, agent_id: str | None = None) -> str:
        """Get status of one or all agents."""
        if agent_id:
            agent = self._agents.get(agent_id)
            if not agent:
                return f"Agent '{agent_id}' not found"
            return json.dumps(agent.to_dict(), indent=2, default=str)

        if not self._agents:
            return "No 24/7 agents configured."

        lines = []
        for aid, agent in self._agents.items():
            state = agent.status.state.upper()
            tasks = agent.status.tasks_completed
            errors = agent.status.errors_count
            tools = len(agent._custom_tool_funcs)
            lines.append(
                f"[{aid}] {state} {agent.config.name} "
                f"(model={agent.config.model}, tools={tools}) | "
                f"tasks: {tasks}, errors: {errors}"
            )
        return "\n".join(lines)

    def list_agents(self) -> list[dict]:
        """List all agents as dicts."""
        return [
            {
                "id": aid,
                "name": agent.config.name,
                "type": agent.config.agent_type,
                "state": agent.status.state,
                "enabled": agent.config.enabled,
                "model": agent.config.model,
                "tools": agent.config.tools,
                "custom_tools_loaded": len(agent._custom_tool_funcs),
                "description": agent.config.description[:100],
                "tasks_completed": agent.status.tasks_completed,
                "errors": agent.status.errors_count,
                "restarts": agent.status.restart_count,
                "check_interval": agent.config.check_interval_minutes,
                "restart_policy": agent.config.restart_policy,
            }
            for aid, agent in self._agents.items()
        ]

    def update_agent(self, agent_id: str, **kwargs) -> str:
        """Update an agent's config."""
        agent = self._agents.get(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found"
        for key, val in kwargs.items():
            if hasattr(agent.config, key):
                setattr(agent.config, key, val)
        self._save_configs()
        return f"Updated agent '{agent.config.name}'"

    async def health_check_all(self) -> dict[str, dict]:
        """Run health check on all agents."""
        results = {}
        for agent_id, agent in self._agents.items():
            health = {
                "name": agent.config.name,
                "state": agent.status.state,
                "healthy": agent.status.state == AgentState.RUNNING,
                "last_heartbeat": agent.status.last_heartbeat,
                "tasks_completed": agent.status.tasks_completed,
                "errors": agent.status.errors_count,
                "custom_tools": len(agent._custom_tool_funcs),
                "uptime": 0.0,
            }
            if agent.status.started_at:
                try:
                    started = datetime.fromisoformat(agent.status.started_at)
                    health["uptime"] = (datetime.now() - started).total_seconds()
                except (ValueError, TypeError):
                    pass
            results[agent_id] = health
        return results

    def get_summary(self) -> str:
        """Get summary of all 24/7 agents."""
        total = len(self._agents)
        running = sum(1 for a in self._agents.values() if a.status.state == AgentState.RUNNING)
        stopped = sum(1 for a in self._agents.values() if a.status.state == AgentState.STOPPED)
        failed = sum(1 for a in self._agents.values() if a.status.state == AgentState.FAILED)
        return (
            f"24/7 Agents: {total} total, {running} running, "
            f"{stopped} stopped, {failed} failed"
        )
