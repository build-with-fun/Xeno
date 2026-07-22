"""Plan-and-Execute Pattern — structured decomposition of complex tasks.

The agent:
1. Decomposes a complex query into a plan (ordered steps)
2. Executes each step sequentially, feeding outputs forward
3. Synthesizes final result from step outputs

Supports step-level parallelism (steps with no dependencies run concurrently).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    result: Any = None
    status: str = "pending"  # pending | running | completed | failed
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status,
            "error": self.error,
            "duration": round(self.end_time - self.start_time, 2) if self.end_time else None,
        }


@dataclass
class PlanResult:
    query: str
    plan: list[PlanStep] = field(default_factory=list)
    final_result: Any = None
    total_time: float = 0.0
    step_count: int = 0
    success_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "plan": [s.to_dict() for s in self.plan],
            "final_result": str(self.final_result)[:500],
            "total_time": round(self.total_time, 2),
            "step_count": self.step_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
        }


async def plan_and_execute(
    query: str,
    plan_fn: Callable[[str], Any],
    execute_fn: Callable[[str, dict[str, Any]], Any],
    synthesize_fn: Optional[Callable[[str, list[PlanStep]], Any]] = None,
    max_concurrent_steps: int = 5,
) -> PlanResult:
    """Run plan-and-execute pattern.

    Args:
        query: The complex query to decompose
        plan_fn: Callable(query) -> list[{"id", "description", "depends_on"}]
        execute_fn: Callable(step_id, context) -> result
        synthesize_fn: Optional Callable(query, steps) -> final_result
        max_concurrent_steps: Max parallel step execution

    Returns:
        PlanResult with plan, step results, and synthesized output
    """
    start = time.time()
    result = PlanResult(query=query)

    raw_plan = await _call_fn(plan_fn, query)
    plan = [PlanStep(**s) if isinstance(s, dict) else s for s in raw_plan]
    result.plan = plan
    result.step_count = len(plan)

    completed: dict[str, Any] = {}
    sem = asyncio.Semaphore(max_concurrent_steps)

    async def run_step(step: PlanStep):
        async with sem:
            step.status = "running"
            step.start_time = time.time()
            try:
                step.result = await _call_fn(execute_fn, step.id, completed)
                step.status = "completed"
                completed[step.id] = step.result
                result.success_count += 1
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                completed[step.id] = f"<ERROR: {e}>"
                result.failed_count += 1
                logger.warning(f"Plan step '{step.id}' failed: {e}")
            finally:
                step.end_time = time.time()

    ready = [s for s in plan if not s.depends_on]
    pending = [s for s in plan if s.depends_on]

    while ready:
        await asyncio.gather(*(run_step(s) for s in ready))

        newly_ready = []
        remaining = []
        for s in pending:
            if all(dep in completed for dep in s.depends_on):
                newly_ready.append(s)
            else:
                remaining.append(s)
        ready = newly_ready
        pending = remaining

    if synthesize_fn:
        result.final_result = await _call_fn(synthesize_fn, query, plan)
    else:
        result.final_result = {s.id: s.result for s in plan}

    result.total_time = time.time() - start
    return result


async def _call_fn(fn: Callable, *args) -> Any:
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args)
    return fn(*args)
