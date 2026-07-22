from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FanOutOrchestrator:
    """Parallel task execution — fan-out to multiple agents, fan-in results.

    Sends the same or different tasks to multiple agents in parallel,
    then aggregates the results. Best for:
    - Parallel research on different aspects of a topic
    - Competitive analysis (multiple angles simultaneously)
    - Validation (same task to multiple agents for comparison)
    """

    def __init__(
        self,
        agent_runner: Optional[Callable[[str, str], Any]] = None,
        max_parallel: int = 5,
    ):
        self._agent_runner = agent_runner
        self.max_parallel = max_parallel

    def set_agent_runner(self, runner: Callable[[str, str], Any]):
        self._agent_runner = runner

    async def execute(
        self,
        tasks: list[dict],
    ) -> list[dict]:
        """Execute multiple tasks in parallel.

        Each task: {"agent": "agent-name", "description": "what to do", "id": "optional-id"}
        """
        if not self._agent_runner:
            raise RuntimeError("No agent runner configured")

        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _run_one(task: dict) -> dict:
            async with semaphore:
                try:
                    result = await self._agent_runner(task["agent"], task["description"])
                    return {
                        "id": task.get("id", task["agent"]),
                        "agent": task["agent"],
                        "output": str(result)[:3000],
                        "success": True,
                    }
                except Exception as e:
                    logger.warning(f"FanOut task {task.get('id', '?')} failed: {e}")
                    return {
                        "id": task.get("id", task["agent"]),
                        "agent": task["agent"],
                        "error": str(e),
                        "success": False,
                    }

        coros = [_run_one(t) for t in tasks]
        results = await asyncio.gather(*coros)

        success_count = sum(1 for r in results if r["success"])
        logger.info(f"FanOut complete: {success_count}/{len(tasks)} succeeded")
        return results

    def aggregate_text(self, results: list[dict]) -> str:
        parts = [f"Completed {len(results)} parallel tasks:"]
        for r in results:
            status = "✓" if r["success"] else "✗"
            parts.append(f"\n{status} {r['agent']}:")
            if r["success"]:
                parts.append(r.get("output", "")[:500])
            else:
                parts.append(r.get("error", ""))
        return "\n".join(parts)
