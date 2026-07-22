from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Sequential pipeline — each agent processes the output of the previous.

    Agent A output → Agent B input → Agent C input → ...

    Best for:
    - Document processing (extract → classify → enrich → route)
    - Content production (research → draft → edit → format)
    - Any workflow where each step depends on the previous output
    """

    def __init__(
        self,
        agent_runner: Optional[Callable[[str, str], Any]] = None,
    ):
        self._agent_runner = agent_runner
        self._results: list[dict] = []

    def set_agent_runner(self, runner: Callable[[str, str], Any]):
        self._agent_runner = runner

    async def execute(
        self,
        steps: list[dict],
        initial_input: str = "",
    ) -> list[dict]:
        """Execute a pipeline of steps.

        Each step: {"agent": "agent-name", "description": "what to do (use {input} for prev output)"}
        """
        if not self._agent_runner:
            raise RuntimeError("No agent runner configured")

        self._results = []
        current_input = initial_input

        for i, step in enumerate(steps):
            description = step["description"].format(input=current_input[:2000])
            logger.info(f"Pipeline step {i+1}/{len(steps)}: {step['agent']}")

            try:
                result = await self._agent_runner(step["agent"], description)
                self._results.append({
                    "step": i,
                    "agent": step["agent"],
                    "input": current_input[:200],
                    "output": str(result)[:2000],
                    "success": True,
                })
                current_input = str(result)
            except Exception as e:
                self._results.append({
                    "step": i,
                    "agent": step["agent"],
                    "input": current_input[:200],
                    "error": str(e),
                    "success": False,
                })
                raise

        return self._results

    @property
    def last_output(self) -> str:
        if self._results:
            return self._results[-1].get("output", "")
        return ""
