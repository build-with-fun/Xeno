from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class AdaptiveOrchestrator:
    """Dynamic plan discovery and routing.

    For open-ended problems where the solution path isn't known upfront.
    The orchestrator:
    1. Analyzes the problem
    2. Creates an initial plan
    3. Executes step by step
    4. Adapts based on intermediate results
    5. Re-plans when obstacles are encountered

    Best for:
    - Research tasks where findings change the direction
    - Debugging where each clue leads to the next
    - Creative work where iteration is expected
    """

    def __init__(
        self,
        agent_runner: Optional[Callable[[str, str], Any]] = None,
        llm: Optional[Any] = None,
        max_steps: int = 10,
    ):
        self._agent_runner = agent_runner
        self._llm = llm
        self.max_steps = max_steps
        self._steps: list[dict] = []

    def set_agent_runner(self, runner: Callable[[str, str], Any]):
        self._agent_runner = runner

    def set_llm(self, llm: Any):
        self._llm = llm

    async def execute(self, goal: str, available_agents: list[str]) -> dict:
        if not self._agent_runner:
            raise RuntimeError("No agent runner configured")

        self._steps = []
        completed = []
        current_goal = goal

        for step_num in range(self.max_steps):
            next_action = await self._plan_next(current_goal, completed, available_agents)
            if next_action is None:
                break

            step_record = {
                "step": step_num + 1,
                "plan": next_action,
                "result": None,
                "success": False,
            }

            try:
                result = await self._agent_runner(
                    next_action.get("agent", available_agents[0]),
                    next_action.get("description", current_goal),
                )
                result_str = str(result)[:2000]
                step_record["result"] = result_str
                step_record["success"] = True
                completed.append({
                    "agent": next_action.get("agent", "?"),
                    "description": next_action.get("description", ""),
                    "result": result_str,
                })
                logger.info(f"Adaptive step {step_num+1}: {next_action.get('agent')} → ok")
            except Exception as e:
                step_record["failed"] = str(e)
                step_record["success"] = False
                logger.warning(f"Adaptive step {step_num+1} failed: {e}")

            self._steps.append(step_record)

            if next_action.get("is_final", False):
                break

            if self._llm:
                current_goal = await self._rephrase_goal(goal, completed)

        return {
            "goal": goal,
            "steps_completed": len([s for s in self._steps if s["success"]]),
            "steps_total": len(self._steps),
            "steps": self._steps,
        }

    async def _plan_next(
        self,
        goal: str,
        completed: list[dict],
        available_agents: list[str],
    ) -> Optional[dict]:
        if not self._llm:
            if not completed:
                return {
                    "agent": available_agents[0],
                    "description": goal,
                    "is_final": True,
                }
            return None

        agents_str = ", ".join(available_agents)
        history = "\n".join(
            f"Step {i+1}: Used {c['agent']} → {c.get('result', '')[:200]}"
            for i, c in enumerate(completed)
        )

        prompt = (
            f"Goal: {goal}\n\n"
            f"Steps completed:\n{history}\n\n"
            f"Available agents: {agents_str}\n"
            "What should the NEXT step be? Output JSON: "
            '{"agent": "agent-name", "description": "what to do in this step", '
            '"is_final": false}'
            "\nSet is_final=true if the goal is achieved."
        )

        try:
            result = await self._llm("You are an adaptive task planner.", prompt)
            import json, re
            result_str = str(result)
            json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Adaptive planning failed: {e}")

        if not completed:
            return {"agent": available_agents[0], "description": goal, "is_final": True}
        return None

    async def _rephrase_goal(self, original: str, completed: list[dict]) -> str:
        if not self._llm:
            return original
        history = "\n".join(f"Used {c['agent']}: {c.get('result', '')[:200]}" for c in completed)
        prompt = (
            f"Original goal: {original}\n\n"
            f"What has been done:\n{history}\n\n"
            "Based on progress so far, rephrase what still needs to be done. "
            "Output ONLY the rephrased goal, 1-2 sentences."
        )
        try:
            result = await self._llm("You are a goal refiner.", prompt)
            return str(result)[:300]
        except Exception:
            return original
