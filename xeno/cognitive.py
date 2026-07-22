"""Cognitive reasoning patterns for the Xeno agent system.

Implements advanced reasoning scaffolds from the deepagents guide:
- Chain-of-Thought (CoT)
- ReAct (Reason + Act)
- Reflexion (self-reflect and improve)
- Self-Refine (iterative refinement)
- Tree-of-Thought (exploration)
- Program-of-Thought (code-based reasoning)
- Adaptive Reasoning (pattern selection based on task)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ReasoningPattern(str, Enum):
    CHAIN_OF_THOUGHT = "chain_of_thought"
    REACT = "react"
    REFLEXION = "reflexion"
    SELF_REFINE = "self_refine"
    TREE_OF_THOUGHT = "tree_of_thought"
    PROGRAM_OF_THOUGHT = "program_of_thought"
    ADAPTIVE = "adaptive"


@dataclass
class ReasoningStep:
    step_number: int
    pattern: ReasoningPattern
    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None
    conclusion: Optional[str] = None
    score: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ReasoningTrace:
    task: str
    pattern: ReasoningPattern
    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    reflection: Optional[str] = None
    confidence: float = 0.0
    iterations: int = 0

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "pattern": self.pattern.value,
            "steps": [
                {
                    "step": s.step_number,
                    "thought": s.thought,
                    "action": s.action,
                    "observation": s.observation,
                    "conclusion": s.conclusion,
                    "score": s.score,
                }
                for s in self.steps
            ],
            "final_answer": self.final_answer,
            "reflection": self.reflection,
            "confidence": self.confidence,
            "iterations": self.iterations,
        }


# System prompts for each reasoning pattern
COT_SYSTEM_PROMPT = """You are a Chain-of-Thought reasoning agent. For every problem:
1. Break the problem into clear, numbered reasoning steps
2. Show your work at each step
3. State what you know and what you need to find
4. Apply logical deductions step by step
5. Arrive at a final answer with confidence level

Format your response as:
THOUGHT: [your reasoning step]
THOUGHT: [next reasoning step]
...
CONCLUSION: [final answer]
CONFIDENCE: [0.0 to 1.0]"""

REACT_SYSTEM_PROMPT = """You are a ReAct reasoning agent that alternates between thinking and acting:
1. THOUGHT: Analyze the current state and decide what to do next
2. ACTION: Choose and execute a tool to gather information
3. OBSERVATION: Examine the tool's result
4. Repeat until you have enough information
5. CONCLUSION: Provide your final answer

Format:
THOUGHT: [what you're thinking]
ACTION: [tool_name(args)]
OBSERVATION: [what you observed]
...
CONCLUSION: [final answer]"""

REFLEXION_SYSTEM_PROMPT = """You are a Reflexion agent that learns from experience:
1. Attempt to solve the task
2. After each attempt, evaluate what went wrong
3. Generate specific, actionable feedback for next attempt
4. Revise your approach based on the feedback
5. Track improvement across attempts

After each attempt provide:
ATTEMPT: [what you tried]
EVALUATION: [what worked, what didn't]
FEEDBACK: [specific improvement suggestions]
REVISED APPROACH: [how you'll do it differently]"""

SELF_REFINE_SYSTEM_PROMPT = """You are a Self-Refine agent that iteratively improves output:
1. Generate an initial response
2. Critically evaluate your own response
3. Identify specific weaknesses or gaps
4. Produce an improved version
5. Repeat until quality is satisfactory

For each iteration:
INITIAL: [first draft]
CRITIQUE: [what's wrong with it]
REFINED: [improved version]
QUALITY_SCORE: [1-10]"""

TOT_SYSTEM_PROMPT = """You are a Tree-of-Thought agent that explores multiple reasoning paths:
1. Generate 2-3 different approaches to solve the problem
2. Evaluate each approach's promise (score 1-10)
3. Explore the most promising path(s) further
4. Prune dead ends
5. Select the best solution

For each thought branch:
BRANCH [id]: [approach description]
SCORE: [promise score 1-10]
FEASIBILITY: [high/medium/low]
...
SELECTED: [best branch id]
FINAL: [solution using best approach]"""

POT_SYSTEM_PROMPT = """You are a Program-of-Thought agent that reasons through code:
1. Write Python code that solves the problem
2. Explain what each section does
3. Include error handling
4. Run the code mentally or actually
5. Present the result

Format:
CODE:
```python
[python code]
```
EXPLANATION: [what the code does]
RESULT: [output/answer]"""


class CognitiveEngine:
    """Advanced reasoning engine supporting multiple cognitive patterns."""

    def __init__(self, model: str = "deepseek:deepseek-chat"):
        self.model = model
        self.traces: list[ReasoningTrace] = []
        self.pattern_prompts = {
            ReasoningPattern.CHAIN_OF_THOUGHT: COT_SYSTEM_PROMPT,
            ReasoningPattern.REACT: REACT_SYSTEM_PROMPT,
            ReasoningPattern.REFLEXION: REFLEXION_SYSTEM_PROMPT,
            ReasoningPattern.SELF_REFINE: SELF_REFINE_SYSTEM_PROMPT,
            ReasoningPattern.TREE_OF_THOUGHT: TOT_SYSTEM_PROMPT,
            ReasoningPattern.PROGRAM_OF_THOUGHT: POT_SYSTEM_PROMPT,
        }

    def get_system_prompt(self, pattern: ReasoningPattern) -> str:
        """Get the system prompt for a reasoning pattern."""
        return self.pattern_prompts.get(pattern, COT_SYSTEM_PROMPT)

    def select_pattern(self, task: str) -> ReasoningPattern:
        """Adaptively select the best reasoning pattern for a task."""
        task_lower = task.lower()

        # Code-related tasks
        if any(kw in task_lower for kw in ["code", "program", "function", "implement", "debug", "script"]):
            return ReasoningPattern.PROGRAM_OF_THOUGHT

        # Tasks requiring exploration
        if any(kw in task_lower for kw in ["explore", "compare", "evaluate", "options", "alternatives"]):
            return ReasoningPattern.TREE_OF_THOUGHT

        # Tasks requiring tool use
        if any(kw in task_lower for kw in ["search", "find", "look up", "research", "fetch", "get data"]):
            return ReasoningPattern.REACT

        # Tasks requiring improvement
        if any(kw in task_lower for kw in ["improve", "refine", "optimize", "enhance", "better"]):
            return ReasoningPattern.SELF_REFINE

        # Complex multi-step problems
        if any(kw in task_lower for kw in ["why", "explain", "analyze", "reason", "prove", "complex"]):
            return ReasoningPattern.CHAIN_OF_THOUGHT

        # Tasks with past failures
        if any(kw in task_lower for kw in ["retry", "again", "failed", "fix", "was wrong"]):
            return ReasoningPattern.REFLEXION

        return ReasoningPattern.CHAIN_OF_THOUGHT

    def create_trace(self, task: str, pattern: Optional[ReasoningPattern] = None) -> ReasoningTrace:
        """Create a new reasoning trace."""
        if pattern is None or pattern == ReasoningPattern.ADAPTIVE:
            pattern = self.select_pattern(task)

        trace = ReasoningTrace(task=task, pattern=pattern)
        self.traces.append(trace)
        return trace

    def add_step(
        self,
        trace: ReasoningTrace,
        thought: str,
        action: Optional[str] = None,
        observation: Optional[str] = None,
        conclusion: Optional[str] = None,
        score: Optional[float] = None,
    ) -> ReasoningStep:
        """Add a reasoning step to a trace."""
        step = ReasoningStep(
            step_number=len(trace.steps) + 1,
            pattern=trace.pattern,
            thought=thought,
            action=action,
            observation=observation,
            conclusion=conclusion,
            score=score,
        )
        trace.steps.append(step)
        trace.iterations += 1
        return step

    def finalize_trace(self, trace: ReasoningTrace, answer: str, confidence: float = 0.8) -> ReasoningTrace:
        """Finalize a reasoning trace with the answer."""
        trace.final_answer = answer
        trace.confidence = confidence
        return trace

    def reflect(self, trace: ReasoningTrace, outcome: str, success: bool) -> str:
        """Generate a reflection on the reasoning process."""
        if success:
            reflection = (
                f"Task '{trace.task[:50]}...' completed successfully using {trace.pattern.value}. "
                f"Reasoning took {trace.iterations} steps with {trace.confidence:.0%} confidence. "
                f"Key insight: {trace.steps[-1].thought if trace.steps else 'N/A'}"
            )
        else:
            reflection = (
                f"Task '{trace.task[:50]}...' failed using {trace.pattern.value}. "
                f"Attempted {trace.iterations} steps. Outcome: {outcome}. "
                f"Should try a different reasoning pattern next time."
            )
        trace.reflection = reflection
        return reflection

    def format_trace(self, trace: ReasoningTrace) -> str:
        """Format a trace for display."""
        lines = [f"=== Reasoning Trace ({trace.pattern.value}) ==="]
        lines.append(f"Task: {trace.task[:100]}")
        lines.append(f"Iterations: {trace.iterations}")
        lines.append("")
        for step in trace.steps:
            lines.append(f"Step {step.step_number}:")
            lines.append(f"  Thought: {step.thought}")
            if step.action:
                lines.append(f"  Action: {step.action}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
            if step.conclusion:
                lines.append(f"  Conclusion: {step.conclusion}")
            if step.score is not None:
                lines.append(f"  Score: {step.score}")
            lines.append("")
        if trace.final_answer:
            lines.append(f"Final Answer: {trace.final_answer}")
        if trace.reflection:
            lines.append(f"Reflection: {trace.reflection}")
        lines.append(f"Confidence: {trace.confidence:.0%}")
        return "\n".join(lines)

    def get_recent_traces(self, limit: int = 5) -> list[ReasoningTrace]:
        """Get recent reasoning traces for context."""
        return self.traces[-limit:]

    def clear_traces(self) -> None:
        """Clear all traces."""
        self.traces.clear()


# Reflexion memory for tracking past failures and improvements
@dataclass
class ReflexionMemory:
    """Stores past reasoning attempts and their outcomes for learning."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def add_entry(
        self,
        task: str,
        pattern: str,
        attempt: str,
        outcome: str,
        success: bool,
        feedback: str = "",
    ) -> None:
        """Add a reflexion memory entry."""
        self.entries.append({
            "task": task,
            "pattern": pattern,
            "attempt": attempt,
            "outcome": outcome,
            "success": success,
            "feedback": feedback,
        })

    def get_similar_failures(self, task_hint: str, limit: int = 5) -> list[dict]:
        """Get past failures that might be relevant to current task."""
        task_words = set(task_hint.lower().split())
        scored = []
        for entry in self.entries:
            if not entry["success"]:
                entry_words = set(entry["task"].lower().split())
                overlap = len(task_words & entry_words)
                scored.append((overlap, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get_successful_patterns(self, task_hint: str) -> dict[str, int]:
        """Count successful patterns for similar tasks."""
        task_words = set(task_hint.lower().split())
        pattern_counts: dict[str, int] = {}
        for entry in self.entries:
            if entry["success"]:
                entry_words = set(entry["task"].lower().split())
                if len(task_words & entry_words) > 0:
                    p = entry["pattern"]
                    pattern_counts[p] = pattern_counts.get(p, 0) + 1
        return pattern_counts

    def to_dict(self) -> list[dict]:
        return self.entries

    def from_dict(self, data: list[dict]) -> None:
        self.entries = data
