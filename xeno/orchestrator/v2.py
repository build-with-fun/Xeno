"""Unified Orchestrator V2 — replaces the 5 separate orchestrator classes.

Uses the AgentPool for true parallel execution. Patterns are MCP tools
the Main Agent chooses, not hardcoded classes.

The Main Agent:
1. Analyzes task
2. Calls orchestrator.to_plan() → gets a DispatchPlan
3. Calls orchestrator.execute(plan) → runs via AgentPool
4. Calls orchestrator.synthesize(results) → gets final summary
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from xeno.pool.agent_pool import AgentPool, get_agent_pool
from xeno.pool.dispatch import AgentDispatch, DispatchPlan, build_dispatch_plan, enhance_prompt
from xeno.pool.scaling import TaskScale, get_scale_for_task

logger = logging.getLogger(__name__)


class OrchestratorV2:
    """Unified orchestrator that delegates to AgentPool for execution."""

    def __init__(self, pool: Optional[AgentPool] = None):
        self.pool = pool or get_agent_pool()
        self._history: list[dict] = []

    def to_plan(self, goal: str, agent_types: list[str],
                prompts: Optional[list[str]] = None,
                pattern: str = "fanout",
                context: str = "",
                task_scales: Optional[list[TaskScale]] = None) -> DispatchPlan:
        """Convert a goal into a dispatch plan."""
        plan = build_dispatch_plan(goal, agent_types, prompts, pattern, context)

        if task_scales:
            for i, dispatch in enumerate(plan.dispatches):
                if i < len(task_scales):
                    dispatch.scale = task_scales[i]

        return plan

    async def execute(self, plan: DispatchPlan) -> list[dict]:
        """Execute a dispatch plan through the AgentPool."""
        results = await self.pool.run_plan(plan)
        result_dicts = [r.to_dict() for r in results]
        self._history.append({"plan_id": plan.id, "goal": plan.goal, "results": result_dicts})
        return result_dicts

    async def execute_simple(self, goal: str, agent_types: list[str],
                              context: str = "") -> list[dict]:
        """Simple execution: auto-create plan and run."""
        plan = self.to_plan(goal, agent_types, context=context)
        return await self.execute(plan)

    def synthesize(self, results: list[dict], goal: str) -> str:
        """Synthesize multiple agent results into a summary string.

        Returns structured text the Main Agent can use for final response.
        """
        if not results:
            return "No results from agents."

        success_count = sum(1 for r in results if r.get("status") == "completed")
        failed_count = sum(1 for r in results if r.get("status") == "failed" or r.get("status") == "error")

        parts = [f"Results for: {goal}"]
        parts.append(f"({success_count} succeeded, {failed_count} failed)")

        for r in results:
            status = "✓" if r.get("status") == "completed" else "✗"
            agent = r.get("agent_type", r.get("dispatch", {}).get("agent_type", "?"))
            result_text = r.get("result", {}).get("result", r.get("error", ""))
            duration = r.get("result", {}).get("duration", 0)
            duration_str = f"({duration:.1f}s)" if duration else ""
            parts.append(f"\n{status} {agent} {duration_str}:")
            if result_text:
                parts.append(str(result_text)[:500])

        return "\n".join(parts)

    def get_history(self, limit: int = 10) -> list[dict]:
        return self._history[-limit:]

    def stats(self) -> dict:
        total = len(self._history)
        all_results = [r for h in self._history for r in h.get("results", [])]
        completed = sum(1 for r in all_results if r.get("status") == "completed")
        failed = sum(1 for r in all_results if r.get("status") in ("failed", "error"))
        return {"total_executions": total, "total_tasks": len(all_results),
                "completed": completed, "failed": failed}
