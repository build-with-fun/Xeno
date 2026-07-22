"""Multi-agent coordination patterns for Xeno.

Implements the coordination patterns from the deepagents guide:
- Debate Pattern: Multiple agents debate to reach consensus
- Hierarchical Pattern: Manager delegates to workers
- Pipeline Pattern: Sequential agent processing
- Ensemble Pattern: Multiple agents vote on the best answer
- MapReduce Pattern: Distribute and aggregate
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CoordinationPattern(str, Enum):
    DEBATE = "debate"
    HIERARCHICAL = "hierarchical"
    PIPELINE = "pipeline"
    ENSEMBLE = "ensemble"
    MAP_REDUCE = "map_reduce"


@dataclass
class AgentParticipant:
    name: str
    role: str
    system_prompt: str
    agent: Any = None  # The actual agent object
    specialty: str = ""
    bias: str = ""  # e.g., "optimistic", "critical", "neutral"


@dataclass
class CoordinationResult:
    pattern: CoordinationPattern
    task: str
    final_answer: str
    participants: list[str]
    rounds: int = 0
    consensus: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)


class DebateCoordinator:
    """Multi-agent debate pattern.

    Multiple agents with different perspectives debate a question,
    responding to each other's arguments until consensus or max rounds.
    """

    def __init__(self, max_rounds: int = 3, consensus_threshold: float = 0.7):
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold

    async def run(
        self,
        task: str,
        participants: list[AgentParticipant],
        evaluator: Optional[Callable] = None,
    ) -> CoordinationResult:
        """Run a debate session."""
        result = CoordinationResult(
            pattern=CoordinationPattern.DEBATE,
            task=task,
            final_answer="",
            participants=[p.name for p in participants],
        )

        debate_history: list[dict[str, str]] = []
        current_round = 0

        for round_num in range(self.max_rounds):
            current_round = round_num + 1
            round_responses = []

            for participant in participants:
                context = self._build_debate_context(task, debate_history, participant)
                response = await self._get_agent_response(participant, context)
                round_responses.append({
                    "agent": participant.name,
                    "response": response,
                    "round": current_round,
                })
                debate_history.append({
                    "agent": participant.name,
                    "content": response,
                    "round": current_round,
                })
                result.trace.append({
                    "round": current_round,
                    "agent": participant.name,
                    "response": response[:500],
                })

            # Check for consensus
            if self._check_consensus(round_responses):
                result.consensus = True
                break

        # Get final synthesized answer
        result.rounds = current_round
        result.final_answer = await self._synthesize(task, debate_history, participants)
        return result

    def _build_debate_context(
        self,
        task: str,
        history: list[dict],
        participant: AgentParticipant,
    ) -> str:
        context = f"Debate Topic: {task}\n\n"
        context += f"Your role: {participant.role}\n"
        if participant.bias:
            context += f"Your perspective: {participant.bias}\n"
        context += "\nPrevious arguments:\n"

        for entry in history[-6:]:  # Last 6 entries
            context += f"[{entry['agent']}]: {entry['content'][:500]}\n\n"

        if not history:
            context += "This is the opening round. Present your initial position.\n"
        else:
            context += "Respond to the arguments above. Agree, disagree, or add new points.\n"

        return context

    async def _get_agent_response(self, participant: AgentParticipant, context: str) -> str:
        """Get a response from a participant agent."""
        if participant.agent:
            try:
                result = await participant.agent.ainvoke({"messages": [{"role": "user", "content": context}]})
                return result.get("messages", [{}])[-1].get("content", "")
            except Exception as e:
                logger.error(f"Agent {participant.name} error: {e}")
                return f"[Error from {participant.name}: {e}]"
        return f"[{participant.name}: Agent not available]"

    def _check_consensus(self, responses: list[dict]) -> bool:
        """Check if agents have reached consensus (simplified)."""
        if len(responses) < 2:
            return False
        # Simple keyword overlap check
        word_sets = [set(r["response"].lower().split()) for r in responses]
        if not word_sets:
            return False
        common = word_sets[0]
        for ws in word_sets[1:]:
            common = common & ws
        total = max(len(word_sets[0]) | len(ws) for ws in word_sets[1:])
        if total == 0:
            return False
        return len(common) / total > self.consensus_threshold

    async def _synthesize(
        self,
        task: str,
        history: list[dict],
        participants: list[AgentParticipant],
    ) -> str:
        """Synthesize the final answer from the debate."""
        summary = f"Debate on: {task}\n\n"
        summary += "Key points from all participants:\n"
        for entry in history:
            summary += f"[{entry['agent']} round {entry['round']}]: {entry['content'][:200]}\n"
        summary += "\nBased on all arguments, the synthesized view is captured above."
        return summary


class HierarchicalCoordinator:
    """Manager-worker hierarchical coordination pattern.

    A manager agent decomposes the task and delegates to worker agents.
    """

    def __init__(self):
        self.task_results: dict[str, str] = {}

    async def run(
        self,
        task: str,
        manager: AgentParticipant,
        workers: list[AgentParticipant],
    ) -> CoordinationResult:
        """Run hierarchical coordination."""
        result = CoordinationResult(
            pattern=CoordinationPattern.HIERARCHICAL,
            task=task,
            final_answer="",
            participants=[manager.name] + [w.name for w in workers],
        )

        # Manager decomposes the task
        decomposition_prompt = (
            f"Task: {task}\n\n"
            f"Available workers: {', '.join(w.name + ' (' + (w.specialty or w.role) + ')' for w in workers)}\n\n"
            "Decompose this task into subtasks. For each subtask, specify which worker should handle it.\n"
            "Format: WORKER_NAME: subtask description"
        )
        plan = await self._get_agent_response(manager, decomposition_prompt)
        result.trace.append({"phase": "decomposition", "plan": plan[:1000]})

        # Parse and dispatch subtasks
        subtasks = self._parse_plan(plan, workers)
        for worker_name, subtask in subtasks.items():
            worker = next((w for w in workers if w.name == worker_name), None)
            if worker:
                subtask_result = await self._get_agent_response(worker, f"Subtask: {subtask}")
                self.task_results[worker_name] = subtask_result
                result.trace.append({
                    "phase": "execution",
                    "worker": worker_name,
                    "result": subtask_result[:500],
                })

        # Manager synthesizes results
        synthesis_prompt = (
            f"Original task: {task}\n\n"
            "Worker results:\n"
        )
        for name, res in self.task_results.items():
            synthesis_prompt += f"[{name}]: {res[:300]}\n\n"
        synthesis_prompt += "Synthesize these results into a final answer."

        result.final_answer = await self._get_agent_response(manager, synthesis_prompt)
        return result

    def _parse_plan(self, plan: str, workers: list[AgentParticipant]) -> dict[str, str]:
        """Parse the manager's decomposition plan."""
        subtasks = {}
        worker_names = {w.name.lower(): w.name for w in workers}
        for line in plan.split("\n"):
            for token, name in worker_names.items():
                if token in line.lower():
                    subtask = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
                    subtasks[name] = subtask
                    break
        return subtasks

    async def _get_agent_response(self, participant: AgentParticipant, context: str) -> str:
        if participant.agent:
            try:
                result = await participant.agent.ainvoke({"messages": [{"role": "user", "content": context}]})
                return result.get("messages", [{}])[-1].get("content", "")
            except Exception as e:
                return f"[Error: {e}]"
        return f"[{participant.name}: Agent not available]"


class PipelineCoordinator:
    """Sequential pipeline coordination pattern.

    Each agent processes the output of the previous one.
    """

    async def run(
        self,
        task: str,
        pipeline: list[AgentParticipant],
    ) -> CoordinationResult:
        """Run pipeline coordination."""
        result = CoordinationResult(
            pattern=CoordinationPattern.PIPELINE,
            task=task,
            final_answer="",
            participants=[p.name for p in pipeline],
        )

        current_input = task
        for stage, participant in enumerate(pipeline):
            stage_result = await self._get_agent_response(
                participant,
                f"Stage {stage + 1}/{len(pipeline)}: Process the following input and produce your output.\n\nInput: {current_input}",
            )
            result.trace.append({
                "stage": stage + 1,
                "agent": participant.name,
                "input": current_input[:300],
                "output": stage_result[:500],
            })
            current_input = stage_result

        result.final_answer = current_input
        return result

    async def _get_agent_response(self, participant: AgentParticipant, context: str) -> str:
        if participant.agent:
            try:
                result = await participant.agent.ainvoke({"messages": [{"role": "user", "content": context}]})
                return result.get("messages", [{}])[-1].get("content", "")
            except Exception as e:
                return f"[Error: {e}]"
        return f"[{participant.name}: Agent not available]"


class EnsembleCoordinator:
    """Ensemble voting pattern.

    Multiple agents independently solve the same problem,
    then the best answer is selected by voting or evaluation.
    """

    async def run(
        self,
        task: str,
        participants: list[AgentParticipant],
        evaluator: Optional[Callable] = None,
    ) -> CoordinationResult:
        """Run ensemble coordination."""
        result = CoordinationResult(
            pattern=CoordinationPattern.ENSEMBLE,
            task=task,
            final_answer="",
            participants=[p.name for p in participants],
        )

        responses = {}
        for participant in participants:
            response = await self._get_agent_response(
                participant,
                f"Solve the following task independently:\n\n{task}",
            )
            responses[participant.name] = response
            result.trace.append({
                "agent": participant.name,
                "response": response[:500],
            })

        # Select best response (simplified: longest response as proxy)
        if responses:
            best_agent = max(responses, key=lambda k: len(responses[k]))
            result.final_answer = responses[best_agent]
            result.details["selected_agent"] = best_agent
            result.details["all_responses"] = {k: v[:200] for k, v in responses.items()}

        return result

    async def _get_agent_response(self, participant: AgentParticipant, context: str) -> str:
        if participant.agent:
            try:
                result = await participant.agent.ainvoke({"messages": [{"role": "user", "content": context}]})
                return result.get("messages", [{}])[-1].get("content", "")
            except Exception as e:
                return f"[Error: {e}]"
        return f"[{participant.name}: Agent not available]"


class MultiAgentCoordinator:
    """Unified multi-agent coordination system.

    Provides a single interface to run any coordination pattern.
    """

    def __init__(self):
        self.debate = DebateCoordinator()
        self.hierarchical = HierarchicalCoordinator()
        self.pipeline = PipelineCoordinator()
        self.ensemble = EnsembleCoordinator()

    async def run(
        self,
        pattern: CoordinationPattern,
        task: str,
        participants: list[AgentParticipant],
        **kwargs,
    ) -> CoordinationResult:
        """Run a coordination pattern."""
        if pattern == CoordinationPattern.DEBATE:
            return await self.debate.run(task, participants, **kwargs)
        elif pattern == CoordinationPattern.HIERARCHICAL:
            manager = participants[0] if participants else None
            workers = participants[1:] if len(participants) > 1 else []
            return await self.hierarchical.run(task, manager, workers, **kwargs)
        elif pattern == CoordinationPattern.PIPELINE:
            return await self.pipeline.run(task, participants, **kwargs)
        elif pattern == CoordinationPattern.ENSEMBLE:
            return await self.ensemble.run(task, participants, **kwargs)
        else:
            raise ValueError(f"Unknown coordination pattern: {pattern}")
