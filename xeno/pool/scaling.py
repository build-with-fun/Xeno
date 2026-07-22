"""Inference-Time Scaling — configures thinking budget, attempts, model per task.

The Main Agent sets scaling parameters based on task complexity.
Simple tasks → fast model, no thinking. Complex tasks → reasoning model, high budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ComplexityLevel(Enum):
    TRIVIAL = "trivial"       # "what's 2+2?" → no agent needed
    SIMPLE = "simple"         # "read a file" → fast model, 0 thinking
    MODERATE = "moderate"     # "research a topic" → standard model, light thinking
    COMPLEX = "complex"       # "build a feature" → reasoning model, medium thinking
    DEEP = "deep"             # "optimize the database" → deep reasoning, high budget
    CRITICAL = "critical"     # "deploy to production" → max verification, step-by-step


@dataclass
class TaskScale:
    """Scaling configuration for a single agent task."""
    thinking_budget: int = 0       # 0=none, 512=light, 2048=medium, 8192=deep
    num_attempts: int = 1          # for self-consistency (run N times, best pick)
    verification_level: int = 0    # 0=none, 1=quick check, 2=step-by-step verification
    model_override: str = ""       # use different model for this task
    temperature: float = 0.7       # 0.0=deterministic, 1.0=creative
    max_tokens: int = 4096         # max response tokens


SCALE_CONFIGS: dict[ComplexityLevel, TaskScale] = {
    ComplexityLevel.TRIVIAL: TaskScale(thinking_budget=0, model_override="", verification_level=0, temperature=0.3, max_tokens=512),
    ComplexityLevel.SIMPLE: TaskScale(thinking_budget=0, verification_level=0, temperature=0.5, max_tokens=2048),
    ComplexityLevel.MODERATE: TaskScale(thinking_budget=512, verification_level=0, temperature=0.7, max_tokens=4096),
    ComplexityLevel.COMPLEX: TaskScale(thinking_budget=2048, num_attempts=2, verification_level=1, temperature=0.7, max_tokens=8192),
    ComplexityLevel.DEEP: TaskScale(thinking_budget=8192, num_attempts=3, verification_level=2, temperature=0.5, max_tokens=16384),
    ComplexityLevel.CRITICAL: TaskScale(thinking_budget=16384, num_attempts=3, verification_level=2, temperature=0.3, max_tokens=32768),
}


def estimate_complexity(prompt: str, context: str = "") -> ComplexityLevel:
    """Estimate task complexity from prompt keywords and length.

    Returns a ComplexityLevel that helps the Main Agent decide scaling.
    """
    prompt_lower = prompt.lower()
    word_count = len(prompt_lower.split())

    trivial_keywords = {"hello", "hi", "thanks", "ok", "yes", "no", "goodbye", "bye"}
    complex_keywords = {"build", "create", "develop", "architect", "design",
                        "optimize", "refactor", "debug", "analyze", "research",
                        "investigate", "implement", "deploy", "migrate"}
    deep_keywords = {"comprehensive", "thorough", "deep", "extensive", "multi-step",
                     "complex", "large", "distributed", "performance", "security"}

    words_set = set(prompt_lower.split())

    if words_set & deep_keywords and word_count > 30:
        return ComplexityLevel.DEEP
    if words_set & complex_keywords and word_count > 15:
        return ComplexityLevel.COMPLEX
    if words_set & complex_keywords:
        return ComplexityLevel.MODERATE
    if prompt_lower.startswith(trivial_keywords) and word_count < 5:
        return ComplexityLevel.TRIVIAL
    if word_count < 10:
        return ComplexityLevel.SIMPLE
    return ComplexityLevel.MODERATE


def get_scale_for_task(agent_type: str, prompt: str, context: str = "") -> TaskScale:
    """Determine the appropriate task scale for a given task."""
    complexity = estimate_complexity(prompt, context)
    scale = SCALE_CONFIGS[complexity]

    agent_scales = {
        "research": ComplexityLevel.MODERATE,
        "coder": ComplexityLevel.COMPLEX,
        "browser": ComplexityLevel.SIMPLE,
        "planner": ComplexityLevel.MODERATE,
        "analyst": ComplexityLevel.MODERATE,
        "whatsapp": ComplexityLevel.SIMPLE,
        "email": ComplexityLevel.SIMPLE,
    }

    agent_complexity = agent_scales.get(agent_type)
    if agent_complexity and agent_complexity.value > complexity.value:
        scale = SCALE_CONFIGS[agent_complexity]

    return scale
