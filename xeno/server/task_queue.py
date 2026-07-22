"""Event-driven task queue with priority, concurrency, and dependency resolution.

Inspired by Codex CLI's submission/event queue architecture:
- Tasks have priorities (0-100) and dependencies
- Workers consume tasks respecting concurrency limits
- Events emitted on state transitions (submitted → running → completed/failed)
- Supports retries with backoff
- Per-task timeout enforcement
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class PrioritizedTask:
    priority: int  # lower = higher priority
    created_at: float
    task_id: str = ""

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


@dataclass
class Task:
    id: str
    name: str
    fn: Callable[[], Awaitable[Any]]
    priority: int = 50
    timeout_seconds: float = 300.0
    max_retries: int = 0
    retry_delay: float = 1.0
    dependencies: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    state: TaskState = TaskState.PENDING
    result: Any = None
    error: str = ""
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: int = 0
    progress: float = 0.0
    progress_message: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "state": self.state.value,
            "error": self.error[:200] if self.error else "",
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "dependencies": self.dependencies,
        }


class TaskEvent:
    def __init__(self, task: Task, event_type: str, message: str = ""):
        self.task = task
        self.event_type = event_type
        self.message = message
        self.timestamp = time.time()


class TaskQueue:
    """Priority queue with dependency resolution and concurrency control."""

    def __init__(self, max_concurrent: int = 5, default_timeout: float = 300.0):
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: set[str] = set()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._listeners: list[Callable[[TaskEvent], None]] = []
        self._worker_task: Optional[asyncio.Task] = None
        self._running_worker = False

    def subscribe(self, callback: Callable[[TaskEvent], None]):
        self._listeners.append(callback)

    def _emit(self, event: TaskEvent):
        for cb in self._listeners:
            try:
                if inspect.iscoroutinefunction(cb):
                    asyncio.ensure_future(cb(event))
                else:
                    cb(event)
            except Exception:
                pass

    def add_task(self, name: str, fn: Callable[[], Awaitable[Any]], **kwargs) -> str:
        tid = kwargs.pop("id", f"t_{uuid.uuid4().hex[:12]}")
        task = Task(
            id=tid,
            name=name,
            fn=fn,
            priority=kwargs.pop("priority", 50),
            timeout_seconds=kwargs.pop("timeout", self.default_timeout),
            max_retries=kwargs.pop("max_retries", 0),
            retry_delay=kwargs.pop("retry_delay", 1.0),
            dependencies=kwargs.pop("dependencies", []),
            metadata=kwargs,
        )
        self._tasks[tid] = task
        self._try_enqueue(task)
        return tid

    def _try_enqueue(self, task: Task):
        blocked = [dep for dep in task.dependencies if dep in self._tasks and self._tasks[dep].state not in (
            TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)]
        if blocked:
            task.state = TaskState.BLOCKED
            self._emit(TaskEvent(task, "blocked", f"Waiting for: {', '.join(blocked)}"))
            return
        task.state = TaskState.QUEUED
        pt = PrioritizedTask(priority=task.priority, created_at=task.created_at, task_id=task.id)
        self._queue.put_nowait(pt)
        self._emit(TaskEvent(task, "queued"))

    def resolve_dependency(self, completed_task_id: str):
        for task in self._tasks.values():
            if task.state == TaskState.BLOCKED and completed_task_id in task.dependencies:
                remaining = [d for d in task.dependencies if d in self._tasks and self._tasks[d].state not in (
                    TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)]
                if not remaining:
                    self._try_enqueue(task)

    async def _execute_task(self, task: Task):
        async with self._semaphore:
            self._running.add(task.id)
            task.state = TaskState.RUNNING
            task.started_at = time.time()
            self._emit(TaskEvent(task, "started"))
            try:
                result = await asyncio.wait_for(task.fn(), timeout=task.timeout_seconds)
                task.result = result
                task.state = TaskState.COMPLETED
                task.completed_at = time.time()
                task.duration_ms = int((task.completed_at - task.started_at) * 1000)
                self._emit(TaskEvent(task, "completed"))
                self.resolve_dependency(task.id)
            except asyncio.TimeoutError:
                task.state = TaskState.TIMEOUT
                task.error = f"Timed out after {task.timeout_seconds}s"
                self._emit(TaskEvent(task, "timeout"))
                await self._handle_retry(task)
            except Exception as e:
                task.state = TaskState.FAILED
                task.error = str(e)
                self._emit(TaskEvent(task, "failed", str(e)))
                await self._handle_retry(task)
            finally:
                self._running.discard(task.id)

    async def _handle_retry(self, task: Task):
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.state = TaskState.PENDING
            self._emit(TaskEvent(task, "retrying", f"Attempt {task.retry_count}/{task.max_retries}"))
            await asyncio.sleep(task.retry_delay * (2 ** (task.retry_count - 1)))
            pt = PrioritizedTask(priority=task.priority + task.retry_count * 5, created_at=time.time(), task_id=task.id)
            await self._queue.put(pt)
        else:
            task.completed_at = time.time()
            task.duration_ms = int((task.completed_at - task.started_at) * 1000)

    async def _worker(self):
        while self._running_worker:
            try:
                pt = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            task = self._tasks.get(pt.task_id)
            if task is None or task.state in (TaskState.CANCELLED,):
                continue
            asyncio.create_task(self._execute_task(task))

    def start(self):
        if self._running_worker:
            return
        self._running_worker = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self, wait_for_running: bool = True):
        self._running_worker = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if wait_for_running and self._running:
            while self._running:
                await asyncio.sleep(0.5)
        # Cancel remaining queued tasks
        for task in self._tasks.values():
            if task.state in (TaskState.QUEUED, TaskState.PENDING, TaskState.BLOCKED):
                task.state = TaskState.CANCELLED

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.state in (TaskState.QUEUED, TaskState.PENDING, TaskState.BLOCKED):
            task.state = TaskState.CANCELLED
            self._emit(TaskEvent(task, "cancelled"))
            return True
        if task.state == TaskState.RUNNING:
            task.state = TaskState.CANCELLED
            self._emit(TaskEvent(task, "cancelled"))
            return True
        return False

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, state: Optional[TaskState] = None) -> list[Task]:
        if state:
            return [t for t in self._tasks.values() if t.state == state]
        return list(self._tasks.values())

    def stats(self) -> dict:
        states = defaultdict(int)
        for t in self._tasks.values():
            states[t.state.value] += 1
        return {
            "total": len(self._tasks),
            "running": len(self._running),
            "max_concurrent": self.max_concurrent,
            "states": dict(states),
        }

    def update_progress(self, task_id: str, progress: float, message: str = ""):
        task = self._tasks.get(task_id)
        if task:
            task.progress = progress
            task.progress_message = message
            self._emit(TaskEvent(task, "progress", message))


# ============================================================================
# Singleton getter
# ============================================================================

_task_queue_instance: TaskQueue | None = None


def get_task_queue() -> TaskQueue | None:
    """Get or create the global task queue singleton."""
    global _task_queue_instance
    if _task_queue_instance is None:
        try:
            _task_queue_instance = TaskQueue()
        except Exception as e:
            logger.warning(f"Failed to create task queue: {e}")
            return None
    return _task_queue_instance


