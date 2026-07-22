"""AgentPool — 500-1000 concurrent agent instances.

The pool manages a set of typed worker agents. Each worker is a separate
deepagents instance with isolated tools, MCP servers, and memory.

Key features:
- Lazy creation: workers created on first use
- Per-type caps: max N workers per type
- Semaphore-gated concurrency
- Task ID tracking with stop/cancel
- Idle worker reuse
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from xeno.pool.worker import WorkerAgent
from xeno.pool.dispatch import AgentDispatch, DispatchPlan
from xeno.pool.scaling import TaskScale, get_scale_for_task

logger = logging.getLogger(__name__)


class RunningTask:
    """A task that is currently executing or has completed."""
    def __init__(self, task_id: str, agent_type: str, prompt: str, dispatch: AgentDispatch):
        self.task_id = task_id
        self.agent_type = agent_type
        self.prompt = prompt
        self.dispatch = dispatch
        self.status = "pending"
        self.result: Optional[dict] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.cancelled = False

    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        if self.started_at:
            return time.time() - self.started_at
        return 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "status": "cancelled" if self.cancelled else self.status,
            "duration": self.duration,
            "prompt_preview": self.prompt[:100],
            "result_preview": str(self.result)[:200] if self.result else "",
        }


class AgentPool:
    """Pool of reusable worker agents for parallel execution."""

    def __init__(self, max_workers: int = 500, max_per_type: int = 20,
                 idle_timeout: float = 300.0):
        self.max_workers = max_workers
        self.max_per_type = max_per_type
        self.idle_timeout = idle_timeout

        self._workers: dict[str, list[WorkerAgent]] = {}
        self._semaphore = asyncio.Semaphore(max_workers)
        self._active_tasks: dict[str, RunningTask] = {}
        self._default_system_prompts: dict[str, str] = {}
        self._default_tools: dict[str, list] = {}
        self._default_mcp_servers: dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    def register_defaults(self, agent_type: str, system_prompt: str,
                          tools: Optional[list] = None,
                          mcp_servers: Optional[list] = None):
        """Register default config for an agent type."""
        self._default_system_prompts[agent_type] = system_prompt
        if tools:
            self._default_tools[agent_type] = tools
        if mcp_servers:
            self._default_mcp_servers[agent_type] = mcp_servers

    async def initialize(self):
        """Pre-warm workers for common agent types."""
        if self._initialized:
            return
        self._initialized = True

        common_types = ["research", "coder", "browser", "planner", "analyst"]
        for agent_type in common_types:
            if agent_type in self._default_system_prompts:
                try:
                    worker = await self._create_worker(agent_type)
                    async with self._lock:
                        self._workers.setdefault(agent_type, []).append(worker)
                except Exception as e:
                    logger.warning(f"Failed to pre-warm {agent_type}: {e}")

        logger.info(f"AgentPool initialized ({self.max_workers} max, pre-warmed {len(common_types)} types)")

    async def _create_worker(self, agent_type: str) -> WorkerAgent:
        """Create a new worker agent."""
        worker_id = f"{agent_type}_{uuid.uuid4().hex[:6]}"
        worker = WorkerAgent(
            agent_type=agent_type,
            worker_id=worker_id,
            model="",  # will be set from config
            system_prompt=self._default_system_prompts.get(agent_type, ""),
            mcp_servers=self._default_mcp_servers.get(agent_type, []),
            tools=self._default_tools.get(agent_type, []),
        )
        await worker.initialize()
        return worker

    async def _get_worker(self, agent_type: str) -> Optional[WorkerAgent]:
        """Get an available worker of the given type, or create one."""
        async with self._lock:
            workers = self._workers.get(agent_type, [])

            idle = [w for w in workers if not w.is_busy]
            if idle:
                return idle[0]

            total = len(workers)
            if total < self.max_per_type:
                worker = await self._create_worker(agent_type)
                workers.append(worker)
                return worker

            total_all = sum(len(ws) for ws in self._workers.values())
            if total_all < self.max_workers:
                worker = await self._create_worker(agent_type)
                self._workers.setdefault(agent_type, []).append(worker)
                return worker

        return None

    async def run(self, dispatch: AgentDispatch) -> RunningTask:
        """Execute a single agent dispatch. Returns a RunningTask."""
        task_id = dispatch.task_id or f"task_{uuid.uuid4().hex[:8]}"
        task = RunningTask(task_id, dispatch.agent_type, dispatch.prompt, dispatch)
        self._active_tasks[task_id] = task

        worker = await self._get_worker(dispatch.agent_type)
        if not worker:
            task.status = "failed"
            task.result = {"error": "No worker available", "success": False}
            return task

        task.status = "running"
        task.started_at = time.time()

        try:
            result = await worker.run(task_id, dispatch.prompt)
            task.result = result
            task.status = "completed" if result.get("success") else "failed"
        except asyncio.CancelledError:
            task.cancelled = True
            task.status = "cancelled"
        except Exception as e:
            task.status = "failed"
            task.result = {"error": str(e), "success": False}
        finally:
            task.completed_at = time.time()

        return task

    async def run_many(self, dispatches: list[AgentDispatch]) -> list[RunningTask]:
        """Execute multiple dispatches in parallel. Returns list of RunningTasks."""
        async def _run_with_sema(dispatch: AgentDispatch) -> RunningTask:
            async with self._semaphore:
                return await self.run(dispatch)

        tasks = [_run_with_sema(d) for d in dispatches]
        return await asyncio.gather(*tasks)

    async def run_plan(self, plan: DispatchPlan) -> list[RunningTask]:
        """Execute a full dispatch plan. Returns list of RunningTasks."""
        results = await self.run_many(plan.dispatches)
        return results

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self._active_tasks.get(task_id)
        if not task or task.cancelled:
            return False
        task.cancelled = True
        task.status = "cancelled"
        return True

    def get_task(self, task_id: str) -> Optional[RunningTask]:
        return self._active_tasks.get(task_id)

    def list_active(self) -> list[dict]:
        return [t.to_dict() for t in self._active_tasks.values()
                if t.status in ("running", "pending")]

    def list_recent(self, limit: int = 20) -> list[dict]:
        all_tasks = list(self._active_tasks.values())
        all_tasks.sort(key=lambda t: t.started_at or 0, reverse=True)
        return [t.to_dict() for t in all_tasks[:limit]]

    def stats(self) -> dict:
        active = sum(1 for t in self._active_tasks.values() if t.status == "running")
        pending = sum(1 for t in self._active_tasks.values() if t.status == "pending")
        completed = sum(1 for t in self._active_tasks.values() if t.status == "completed")
        failed = sum(1 for t in self._active_tasks.values() if t.status == "failed")
        cancelled = sum(1 for t in self._active_tasks.values() if t.cancelled)
        total_workers = sum(len(ws) for ws in self._workers.values())
        busy_workers = sum(1 for ws in self._workers.values() for w in ws if w.is_busy)

        return {
            "active_tasks": active,
            "pending_tasks": pending,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "cancelled_tasks": cancelled,
            "total_workers": total_workers,
            "busy_workers": busy_workers,
            "idle_workers": total_workers - busy_workers,
            "max_workers": self.max_workers,
        }

    async def shutdown(self):
        """Graceful shutdown of all workers."""
        for workers in self._workers.values():
            for w in workers:
                try:
                    await w.cleanup()
                except Exception:
                    pass
        self._workers.clear()
        self._active_tasks.clear()

    async def _cleanup_idle(self):
        """Periodically clean up idle workers (called by manager)."""
        while True:
            await asyncio.sleep(60)
            async with self._lock:
                for agent_type, workers in list(self._workers.items()):
                    self._workers[agent_type] = [
                        w for w in workers
                        if w.is_busy or w.idle_time < self.idle_timeout
                    ]


_pool_instance: Optional[AgentPool] = None


def get_agent_pool() -> AgentPool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = AgentPool()
    return _pool_instance
