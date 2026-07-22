"""Worker Agent — a single deepagents agent instance with isolated tools/MCP.

Each worker is a separate deepagents agent with its own:
- MemorySaver checkpointer
- MCP server connections
- Tool configuration
- Task state tracking
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from xeno.mcp.adapter import ToolMCPServer, get_server

logger = logging.getLogger(__name__)


class WorkerAgent:
    """A single worker agent instance that can execute tasks."""

    def __init__(self, agent_type: str, worker_id: str,
                 model: str, system_prompt: str,
                 mcp_servers: list[ToolMCPServer] | None = None,
                 tools: list | None = None):
        self.agent_type = agent_type
        self.worker_id = worker_id
        self.model = model
        self.system_prompt = system_prompt
        self.mcp_servers = mcp_servers or []
        self._tools = tools or []
        self._deep_agent: Any = None
        self._checkpointer = MemorySaver()
        self._busy = False
        self._current_task_id: Optional[str] = None
        self._last_used = time.time()
        self._created_at = time.time()
        self._initialized = False

    async def initialize(self):
        """Create the deepagents agent instance."""
        if self._initialized:
            return

        flattened_tools = list(self._tools)
        for srv in self.mcp_servers:
            for tool_name in srv.tool_names:
                tool_func = getattr(srv, f"_call_{tool_name}", None)
                if tool_func:
                    flattened_tools.append(tool_func)

        try:
            self._deep_agent = create_deep_agent(
                model=self.model,
                tools=flattened_tools or None,
                system_prompt=self.system_prompt,
                checkpointer=self._checkpointer,
                name=f"worker_{self.agent_type}_{self.worker_id}",
            )
            self._initialized = True
            logger.info(f"Worker {self.worker_id} ({self.agent_type}) initialized")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} init failed: {e}")
            raise

    @property
    def is_busy(self) -> bool:
        return self._busy

    @property
    def idle_time(self) -> float:
        return time.time() - self._last_used if not self._busy else 0

    @property
    def age_seconds(self) -> float:
        return time.time() - self._created_at

    async def run(self, task_id: str, prompt: str, config: Optional[dict] = None) -> dict:
        """Execute a task. Returns result dict."""
        if not self._initialized:
            await self.initialize()

        self._busy = True
        self._current_task_id = task_id
        start = time.time()

        try:
            result = await self._deep_agent.ainvoke(
                {"messages": [HumanMessage(content=prompt)]},
                config={
                    "configurable": {"thread_id": f"worker_{self.worker_id}_{task_id}"},
                    "recursion_limit": config.get("recursion_limit", 100) if config else 100,
                },
            )
            messages = result.get("messages", [])
            final_text = self._extract_response(messages)
            duration = time.time() - start
            return {
                "task_id": task_id,
                "success": True,
                "result": final_text,
                "duration": duration,
                "worker_id": self.worker_id,
            }
        except Exception as e:
            duration = time.time() - start
            logger.warning(f"Worker {self.worker_id} task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "success": False,
                "error": str(e),
                "duration": duration,
                "worker_id": self.worker_id,
            }
        finally:
            self._busy = False
            self._current_task_id = None
            self._last_used = time.time()

    def _extract_response(self, messages: list) -> str:
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "ai":
                content = msg.content
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    return "".join(text_parts)
                return str(content) if content else "(empty response)"
        return "(no ai response)"

    def get_status(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "agent_type": self.agent_type,
            "busy": self._busy,
            "initialized": self._initialized,
            "current_task": self._current_task_id,
            "idle_seconds": self.idle_time,
            "age_seconds": self.age_seconds,
        }

    async def cleanup(self):
        """Release resources."""
        self._deep_agent = None
        self._initialized = False
        self._busy = False
