"""Tests for the event-driven task queue."""

import asyncio
import pytest
from xeno.server.task_queue import TaskQueue, TaskState, TaskEvent


class TestTaskQueue:
    def test_init(self):
        q = TaskQueue(max_concurrent=3)
        assert q.max_concurrent == 3
        assert q.stats()["total"] == 0

    def test_add_task(self):
        q = TaskQueue()
        async def dummy():
            return 42
        tid = q.add_task("test", dummy)
        assert tid is not None
        assert q.stats()["total"] == 1
        task = q.get_task(tid)
        assert task is not None
        assert task.name == "test"
        assert task.state == TaskState.QUEUED

    def test_task_default_state(self):
        q = TaskQueue()
        async def dummy():
            pass
        tid = q.add_task("default", dummy)
        task = q.get_task(tid)
        assert task.state == TaskState.QUEUED

    def test_list_tasks_empty(self):
        q = TaskQueue()
        assert q.list_tasks() == []
        assert q.list_tasks(state=TaskState.PENDING) == []

    def test_list_tasks_by_state(self):
        q = TaskQueue()
        async def dummy():
            pass
        q.add_task("t1", dummy)
        q.add_task("t2", dummy, priority=10)
        all_tasks = q.list_tasks()
        assert len(all_tasks) == 2
        queued = q.list_tasks(state=TaskState.QUEUED)
        assert len(queued) == 2

    def test_cancel_queued(self):
        q = TaskQueue()
        async def dummy():
            await asyncio.sleep(10)
        tid = q.add_task("cancel-me", dummy)
        assert q.cancel(tid)
        task = q.get_task(tid)
        assert task.state == TaskState.CANCELLED

    def test_cancel_nonexistent(self):
        q = TaskQueue()
        assert not q.cancel("nonexistent")

    def test_dependency_blocking(self):
        q = TaskQueue()
        async def dummy():
            return "ok"
        dep_id = q.add_task("dependency", dummy)
        blocked_id = q.add_task("blocked", dummy, dependencies=[dep_id])
        blocked = q.get_task(blocked_id)
        assert blocked.state == TaskState.BLOCKED

    def test_dependency_resolve_on_complete(self):
        q = TaskQueue()
        async def dummy():
            return "ok"
        dep_id = q.add_task("dependency", dummy)
        blocked_id = q.add_task("blocked", dummy, dependencies=[dep_id])
        blocked = q.get_task(blocked_id)
        assert blocked.state == TaskState.BLOCKED
        # Mark dependency completed then resolve
        q._tasks[dep_id].state = TaskState.COMPLETED
        q.resolve_dependency(dep_id)
        blocked = q.get_task(blocked_id)
        assert blocked.state == TaskState.QUEUED

    async def test_task_execution(self):
        q = TaskQueue(max_concurrent=5)
        results = []
        async def worker():
            results.append("done")
            return "result"
        tid = q.add_task("exec", worker)
        q.start()
        await asyncio.sleep(0.3)
        await q.stop(wait_for_running=True)
        task = q.get_task(tid)
        assert task is not None
        assert task.state == TaskState.COMPLETED

    def test_update_progress(self):
        q = TaskQueue()
        async def dummy():
            return "ok"
        tid = q.add_task("progress", dummy)
        q.update_progress(tid, 0.5, "halfway")
        task = q.get_task(tid)
        assert task.progress == 0.5
        assert task.progress_message == "halfway"

    def test_events(self):
        q = TaskQueue()
        events = []
        def listener(ev: TaskEvent):
            events.append(ev.event_type)
        q.subscribe(listener)
        async def dummy():
            return "ok"
        q.add_task("event-test", dummy)
        assert len(events) >= 1
        assert "queued" in events

    async def test_parallel_execution(self):
        q = TaskQueue(max_concurrent=3)
        results = set()
        async def slow_task(name):
            results.add(name)
            await asyncio.sleep(0.2)
            return name
        q.add_task("a", lambda: slow_task("a"))
        q.add_task("b", lambda: slow_task("b"))
        q.add_task("c", lambda: slow_task("c"))
        q.start()
        await asyncio.sleep(0.05)
        all_running = "running" in q.stats()["states"]
        await asyncio.sleep(0.4)
        await q.stop(wait_for_running=True)
        assert len(results) == 3


class TestTaskState:
    def test_all_states_present(self):
        states = [s.value for s in TaskState]
        expected = ["pending", "queued", "running", "completed", "failed", "cancelled", "timeout", "blocked"]
        for exp in expected:
            assert exp in states
