"""Reflexion Pattern — self-critique and iterative improvement.

The agent:
1. Generates an initial response
2. Evaluates it against criteria (self-critique)
3. Revises based on critique
4. Repeats for N iterations or until quality threshold met
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReflexionResult:
    query: str
    iterations: list[dict] = field(default_factory=list)
    best_response: str = ""
    best_score: float = 0.0
    total_time: float = 0.0
    iteration_count: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "iterations": self.iterations,
            "best_response": self.best_response,
            "best_score": self.best_score,
            "total_time": self.total_time,
            "iteration_count": self.iteration_count,
        }


async def reflexion(
    query: str,
    generate_fn: Callable[[str], Any],
    critique_fn: Callable[[str, str], Any],
    max_iterations: int = 3,
    improvement_threshold: float = 0.9,
    max_tokens_per_step: int = 2000,
) -> ReflexionResult:
    """Run reflexion pattern: generate → critique → revise → repeat.

    Args:
        query: The user's original query
        generate_fn: Callable(query) -> response string
        critique_fn: Callable(query, response) -> (score: float, feedback: str)
        max_iterations: Max refinement cycles
        improvement_threshold: Score at which to stop early (0.0-1.0)
        max_tokens_per_step: Max tokens per generation step

    Returns:
        ReflexionResult with best response and iteration history
    """
    start = time.time()
    result = ReflexionResult(query=query)

    current_response = ""
    best_response = ""
    best_score = 0.0

    for i in range(max_iterations):
        iter_start = time.time()

        if i == 0:
            current_response = await _call_fn(generate_fn, query)
        else:
            revise_prompt = (
                f"Original query: {query}\n\n"
                f"Previous response: {current_response}\n\n"
                f"Feedback: {last_feedback}\n\n"
                f"Revise the response to address the feedback."
            )
            current_response = await _call_fn(generate_fn, revise_prompt)

        score, feedback = await _call_fn(critique_fn, query, current_response)

        iter_time = time.time() - iter_start
        iteration_record = {
            "iteration": i + 1,
            "response": current_response[:max_tokens_per_step],
            "score": score,
            "feedback": feedback,
            "time_seconds": round(iter_time, 2),
        }
        result.iterations.append(iteration_record)

        if score > best_score:
            best_score = score
            best_response = current_response

        last_feedback = feedback

        if score >= improvement_threshold:
            logger.info(f"Reflexion: improvement threshold {improvement_threshold} met at iteration {i+1}")
            break

    result.best_response = best_response
    result.best_score = best_score
    result.iteration_count = len(result.iterations)
    result.total_time = time.time() - start

    return result


async def _call_fn(fn: Callable, *args) -> Any:
    """Call a function, handling both sync and async."""
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args)
    return fn(*args)


import asyncio
