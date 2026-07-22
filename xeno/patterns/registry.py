"""Agentic Pattern Registry — registers all patterns as MCP-callable tools.

Each pattern is wrapped as a tool the Main Agent can invoke via MCP.
Patterns are metacognition tools — the Main Agent uses them when
it determines a problem requires structured reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from xeno.patterns.reflexion import reflexion as _reflexion
from xeno.patterns.plan_execute import plan_and_execute as _plan_execute
from xeno.patterns.tree_of_thoughts import tree_of_thoughts as _tree_of_thoughts
from xeno.patterns.self_consistency import self_consistency as _self_consistency

logger = logging.getLogger(__name__)

# Pattern registry: name -> (handler, description, parameters_schema)
_patterns: dict[str, dict] = {}


def register_pattern(
    name: str,
    handler: Callable,
    description: str,
    parameters: Optional[list[dict]] = None,
):
    """Register a metacognition pattern.

    Args:
        name: Pattern name (e.g. "reflexion", "tree_of_thoughts")
        handler: Async callable that implements the pattern
        description: Human-readable description
        parameters: JSON schema for parameters
    """
    _patterns[name] = {
        "handler": handler,
        "description": description,
        "parameters": parameters or [],
    }
    logger.info(f"Registered pattern: {name}")


def get_pattern(name: str) -> Optional[dict]:
    return _patterns.get(name)


def list_patterns() -> dict[str, dict]:
    """List all registered patterns (without handlers)."""
    return {
        name: {
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in _patterns.items()
    }


async def call_pattern(name: str, **kwargs) -> dict:
    """Call a pattern by name with keyword args."""
    info = _patterns.get(name)
    if not info:
        raise ValueError(f"Unknown pattern: {name}")
    handler = info["handler"]
    result = await handler(**kwargs)
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return result


def register_default_patterns():
    """Register all built-in patterns."""
    register_pattern(
        "reflexion",
        _reflexion,
        "Self-critique and iterative improvement. Generate → evaluate → revise → repeat. "
        "Best for debugging, writing, and open-ended generation tasks.",
        parameters=[
            {"name": "query", "type": "string", "description": "The user's original query"},
            {"name": "max_iterations", "type": "integer", "description": "Max refinement cycles", "default": 3},
            {"name": "improvement_threshold", "type": "number", "description": "Score to stop early", "default": 0.9},
        ],
    )

    register_pattern(
        "plan_and_execute",
        _plan_execute,
        "Decompose complex tasks into steps, execute with dependency resolution. "
        "Best for multi-step research, data pipelines, and sequential tasks.",
        parameters=[
            {"name": "query", "type": "string", "description": "The complex query to decompose"},
            {"name": "max_concurrent_steps", "type": "integer", "description": "Max parallel steps", "default": 5},
        ],
    )

    register_pattern(
        "tree_of_thoughts",
        _tree_of_thoughts,
        "Explore multiple reasoning paths with branching, evaluation, and pruning. "
        "Best for planning, strategy, creative problem-solving, and complex reasoning.",
        parameters=[
            {"name": "query", "type": "string", "description": "The query to explore"},
            {"name": "branching_factor", "type": "integer", "description": "Candidates per expansion", "default": 3},
            {"name": "beam_width", "type": "integer", "description": "Top candidates kept per level", "default": 2},
            {"name": "max_depth", "type": "integer", "description": "Maximum depth of exploration", "default": 3},
        ],
    )

    register_pattern(
        "self_consistency",
        _self_consistency,
        "Run N independent attempts, evaluate, pick best. "
        "Best for factual recall, math, code generation, and any task needing accuracy.",
        parameters=[
            {"name": "query", "type": "string", "description": "The query to answer"},
            {"name": "n_attempts", "type": "integer", "description": "Number of independent attempts", "default": 5},
            {"name": "concurrency", "type": "integer", "description": "Max parallel attempts", "default": 3},
        ],
    )

    logger.info(f"Registered {len(_patterns)} metacognition patterns")
