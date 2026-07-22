from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """Multi-agent debate for verification and quality improvement.

    Two or more agents discuss a topic/question from different perspectives,
    then a judge agent synthesizes the best answer.

    Best for:
    - Fact-checking and verification
    - Complex reasoning with multiple valid viewpoints
    - Quality assurance before delivering results
    - Consensus-building on uncertain topics
    """

    def __init__(
        self,
        agent_runner: Optional[Callable[[str, str], Any]] = None,
        judge_llm: Optional[Any] = None,
    ):
        self._agent_runner = agent_runner
        self._judge_llm = judge_llm
        self._rounds: list[list[str]] = []

    def set_agent_runner(self, runner: Callable[[str, str], Any]):
        self._agent_runner = runner

    def set_judge(self, llm: Any):
        self._judge_llm = llm

    async def debate(
        self,
        topic: str,
        agents: list[str],
        rounds: int = 2,
        perspectives: Optional[list[str]] = None,
    ) -> dict:
        if not self._agent_runner:
            raise RuntimeError("No agent runner configured")

        if perspectives is None:
            perspectives = [
                "Argue FOR the proposition",
                "Argue AGAINST the proposition",
                "Provide a neutral analysis",
            ]

        self._rounds = []

        for round_num in range(rounds):
            round_args = []
            for i, agent in enumerate(agents[:len(perspectives)]):
                perspective = perspectives[i % len(perspectives)]
                context = ""
                if self._rounds:
                    context = "\n\nPrevious round arguments:\n" + "\n".join(self._rounds[-1])
                description = f"Topic: {topic}\n\nYour perspective: {perspective}\n\nRound {round_num + 1}/{rounds}{context}\n\nPresent your argument."
                round_args.append({"agent": agent, "description": description})

            round_results = []
            for arg in round_args:
                try:
                    result = await self._agent_runner(arg["agent"], arg["description"])
                    round_results.append(str(result))
                except Exception as e:
                    logger.warning(f"Debate round {round_num}, agent {arg['agent']} failed: {e}")
                    round_results.append(f"[Error: {e}]")

            self._rounds.append(round_results)

        verdict = await self._judge_debate(topic)
        return {
            "topic": topic,
            "rounds": self._rounds,
            "verdict": verdict,
        }

    async def _judge_debate(self, topic: str) -> str:
        if not self._judge_llm:
            return "No judge configured"

        transcript = []
        for r, round_args in enumerate(self._rounds):
            for a, arg in enumerate(round_args):
                transcript.append(f"Round {r+1}, Agent {a+1}: {arg[:300]}")

        prompt = (
            f"Topic debated: {topic}\n\n"
            f"Transcript:\n" + "\n".join(transcript) + "\n\n"
            "As a neutral judge, synthesize the best answer from these arguments. "
            "Identify points of agreement, key disagreements, and your final verdict. "
            "Output concise, actionable conclusions."
        )

        try:
            result = await self._judge_llm(
                "You are an impartial judge evaluating a multi-agent debate.",
                prompt,
            )
            return str(result)[:2000]
        except Exception as e:
            logger.warning(f"Judge failed: {e}")
            return f"Judge error: {e}"
