from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DelegatedTask:
    id: str
    name: str
    agent_name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class DelegationPlan:
    goal: str
    tasks: list[DelegatedTask] = field(default_factory=list)
    reasoning: str = ""


class SupervisorOrchestrator:
    """Central coordinator that delegates subtasks to specialized agents.

    The supervisor:
    1. Receives a complex goal
    2. Decomposes it into subtasks
    3. Delegates each subtask to the appropriate specialist agent
    4. Monitors progress
    5. Aggregates results into a final response

    This mirrors how Hermes Agent and production multi-agent systems work.
    """

    def __init__(
        self,
        max_parallel: int = 3,
        agent_runner: Optional[Callable[[str, str], Any]] = None,
    ):
        self.max_parallel = max_parallel
        self._agent_runner = agent_runner
        self._tasks: dict[str, DelegatedTask] = {}
        self._llm = None

    def set_llm(self, llm: Any):
        self._llm = llm

    def set_agent_runner(self, runner: Callable[[str, str], Any]):
        self._agent_runner = runner

    async def plan(self, goal: str, available_agents: list[str]) -> DelegationPlan:
        if self._llm:
            return await self._plan_with_llm(goal, available_agents)
        return self._plan_simple(goal, available_agents)

    async def _plan_with_llm(self, goal: str, available_agents: list[str]) -> DelegationPlan:
        agents_str = "\n".join(f"- {a}" for a in available_agents)
        prompt = (
            f"User goal: {goal}\n\n"
            f"Available agents:\n{agents_str}\n\n"
            "Decompose this goal into subtasks and assign each to the best agent.\n"
            "Output as JSON: {\"reasoning\": \"...\", \"tasks\": [{\"name\": \"...\", "
            "\"agent\": \"agent-name\", \"description\": \"what to do\"}]}"
        )
        try:
            result = await self._llm("You are a task planning supervisor.", prompt)
            import json
            import re
            result_str = str(result)
            json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                plan = DelegationPlan(goal=goal, reasoning=data.get("reasoning", ""))
                for i, t in enumerate(data.get("tasks", [])):
                    plan.tasks.append(DelegatedTask(
                        id=f"task_{i}",
                        name=t.get("name", f"Task {i}"),
                        agent_name=t.get("agent", available_agents[0] if available_agents else "unknown"),
                        description=t.get("description", ""),
                    ))
                return plan
        except Exception as e:
            logger.warning(f"LLM planning failed: {e}")

        return self._plan_simple(goal, available_agents)

    def _plan_simple(self, goal: str, available_agents: list[str]) -> DelegationPlan:
        plan = DelegationPlan(goal=goal, reasoning="Simple round-robin delegation")
        for i, agent in enumerate(available_agents[:3]):
            plan.tasks.append(DelegatedTask(
                id=f"task_{i}",
                name=f"{agent} task",
                agent_name=agent,
                description=f"Handle part of: {goal[:100]}",
            ))
        return plan

    async def execute(self, plan: DelegationPlan) -> dict[str, Any]:
        if not self._agent_runner:
            logger.error("No agent runner configured")
            return {"error": "No agent runner"}

        results = {}
        running: list[asyncio.Task] = []
        task_queue = list(plan.tasks)

        while task_queue or running:
            while len(running) < self.max_parallel and task_queue:
                task = task_queue.pop(0)
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._tasks[task.id] = task

                async def _run(t: DelegatedTask):
                    try:
                        result = await self._agent_runner(t.agent_name, t.description)
                        t.status = TaskStatus.COMPLETED
                        t.result = result
                        t.completed_at = datetime.now().isoformat()
                        results[t.name] = result
                    except Exception as e:
                        t.status = TaskStatus.FAILED
                        t.error = str(e)
                        results[t.name] = f"Error: {e}"

                running.append(asyncio.create_task(_run(task)))

            if running:
                done, running = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
                running = list(running)

        return results

    def get_status(self) -> dict:
        return {
            "total": len(self._tasks),
            "completed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            "running": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
        }
