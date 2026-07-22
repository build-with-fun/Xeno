"""Self-Consistency Pattern — multiple independent attempts, best answer.

The agent:
1. Runs N independent generation attempts (with temperature/seed variation)
2. Evaluates each against criteria
3. Picks the best response (highest score)
4. Optionally ensembles/majority-votes structured outputs

Ideal for mathematical reasoning, code generation, factual recall.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Attempt:
    index: int
    response: str
    score: float
    feedback: str = ""
    time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "response": self.response[:200],
            "score": self.score,
            "feedback": self.feedback[:100],
            "time_seconds": round(self.time_seconds, 2),
        }


@dataclass
class SelfConsistencyResult:
    query: str
    attempts: list[Attempt] = field(default_factory=list)
    best_response: str = ""
    best_score: float = 0.0
    avg_score: float = 0.0
    consensus_answer: Optional[str] = None
    total_time: float = 0.0
    attempt_count: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "attempt_count": self.attempt_count,
            "best_score": self.best_score,
            "avg_score": round(self.avg_score, 3),
            "best_response": self.best_response[:300],
            "consensus_answer": self.consensus_answer,
            "total_time": round(self.total_time, 2),
            "attempts": [a.to_dict() for a in self.attempts],
        }


async def self_consistency(
    query: str,
    generate_fn: Callable[[str], Any],
    evaluate_fn: Callable[[str, str], Any],
    n_attempts: int = 5,
    extract_answer_fn: Optional[Callable[[str], str]] = None,
    concurrency: int = 3,
) -> SelfConsistencyResult:
    """Run self-consistency pattern.

    Args:
        query: The query to answer
        generate_fn: Callable(query) -> response string
        evaluate_fn: Callable(query, response) -> (score: float, feedback: str)
        n_attempts: Number of independent attempts
        extract_answer_fn: Optional fn to extract structured answer for consensus
        concurrency: Max concurrent generation calls

    Returns:
        SelfConsistencyResult with best attempt and consensus
    """
    start = time.time()
    result = SelfConsistencyResult(query=query)

    sem = asyncio.Semaphore(concurrency)

    async def run_attempt(idx: int) -> Attempt:
        async with sem:
            t0 = time.time()
            response = await _call_fn(generate_fn, query)
            score, feedback = await _call_fn(evaluate_fn, query, response)
            elapsed = time.time() - t0
            return Attempt(
                index=idx,
                response=response,
                score=score,
                feedback=feedback,
                time_seconds=elapsed,
            )

    attempts = await asyncio.gather(*(run_attempt(i) for i in range(n_attempts)))
    result.attempts = attempts
    result.attempt_count = len(attempts)

    # Best by score
    best = max(attempts, key=lambda a: a.score)
    result.best_response = best.response
    result.best_score = best.score
    result.avg_score = sum(a.score for a in attempts) / len(attempts)

    # Consensus via extracted answers
    if extract_answer_fn:
        answers = []
        for a in attempts:
            try:
                extracted = extract_answer_fn(a.response)
                if extracted:
                    answers.append(extracted)
            except Exception:
                pass
        if answers:
            counter = Counter(answers)
            most_common = counter.most_common(1)
            if most_common:
                result.consensus_answer = most_common[0][0]

    result.total_time = time.time() - start
    return result


async def _call_fn(fn: Callable, *args) -> Any:
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args)
    return fn(*args)
