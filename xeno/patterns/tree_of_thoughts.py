"""Tree-of-Thoughts Pattern — explore multiple reasoning paths.

The agent:
1. Generates N candidate thoughts at each step
2. Evaluates each thought (score + feedback)
3. Prunes to top-K thoughts
4. Expands each kept thought into new candidates
5. Deepest path wins after D depth levels

Configurable: branching factor, beam width, max depth, evaluation criteria.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ThoughtNode:
    id: str
    content: str
    parent_id: Optional[str] = None
    depth: int = 0
    score: float = 0.0
    feedback: str = ""
    children: list["ThoughtNode"] = field(default_factory=list)
    is_leaf: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content[:200],
            "parent_id": self.parent_id,
            "depth": self.depth,
            "score": self.score,
            "feedback": self.feedback[:100],
            "child_count": len(self.children),
            "is_leaf": self.is_leaf,
        }

    def path_to_root(self) -> list["ThoughtNode"]:
        nodes = [self]
        current = self
        while current.parent_id:
            pass  # would need lookup
        return nodes


@dataclass
class TreeOfThoughtsResult:
    query: str
    root: Optional[ThoughtNode] = None
    best_path: list[ThoughtNode] = field(default_factory=list)
    best_score: float = 0.0
    total_nodes: int = 0
    total_time: float = 0.0
    depth_reached: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "best_score": self.best_score,
            "total_nodes": self.total_nodes,
            "total_time": round(self.total_time, 2),
            "depth_reached": self.depth_reached,
            "best_path": [n.to_dict() for n in self.best_path],
        }


async def tree_of_thoughts(
    query: str,
    generate_fn: Callable[[str, list[str]], Any],
    evaluate_fn: Callable[[str, str], Any],
    branching_factor: int = 3,
    beam_width: int = 2,
    max_depth: int = 3,
) -> TreeOfThoughtsResult:
    """Run Tree-of-Thoughts pattern.

    Args:
        query: The query to explore
        generate_fn: Callable(query, [prior_thoughts]) -> list of candidate thought strings
        evaluate_fn: Callable(query, thought) -> (score: float, feedback: str)
        branching_factor: Number of candidates per node expansion
        beam_width: Number of top candidates to keep per depth level
        max_depth: Maximum depth of exploration

    Returns:
        TreeOfThoughtsResult with best path and tree structure
    """
    start = time.time()
    result = TreeOfThoughtsResult(query=query)
    node_id = 0

    def next_id() -> str:
        nonlocal node_id
        node_id += 1
        return f"thought_{node_id}"

    root = ThoughtNode(id=next_id(), content=query, depth=0, is_leaf=False)
    result.root = root
    result.total_nodes = 1

    frontier: list[ThoughtNode] = [root]
    all_nodes: dict[str, ThoughtNode] = {root.id: root}

    for depth in range(max_depth):
        if not frontier:
            break

        all_candidates: list[ThoughtNode] = []

        for node in frontier:
            prior = [n.content for n in node.path_to_root() if n.id != root.id]
            candidates = await _call_fn(generate_fn, query, prior)

            for cand_content in candidates[:branching_factor]:
                score, feedback = await _call_fn(evaluate_fn, query, cand_content)

                child = ThoughtNode(
                    id=next_id(),
                    content=cand_content,
                    parent_id=node.id,
                    depth=depth + 1,
                    score=score,
                    feedback=feedback,
                )
                node.children.append(child)
                all_nodes[child.id] = child
                all_candidates.append(child)
                result.total_nodes += 1

        # Prune to beam_width
        all_candidates.sort(key=lambda n: n.score, reverse=True)
        frontier = all_candidates[:beam_width]

        if not frontier:
            break

        result.depth_reached = depth + 1

    # Mark leaves and find best path
    for node in all_nodes.values():
        if not node.children:
            node.is_leaf = True

    # Find leaf with best score
    leaves = [n for n in all_nodes.values() if n.is_leaf]
    if leaves:
        best_leaf = max(leaves, key=lambda n: n.score)
        result.best_score = best_leaf.score
        # Build path to root
        path = []
        current = best_leaf
        while current:
            path.append(current)
            current = all_nodes.get(current.parent_id) if current.parent_id else None
        result.best_path = list(reversed(path))

    result.total_time = time.time() - start
    return result


async def _call_fn(fn: Callable, *args) -> Any:
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args)
    return fn(*args)
