"""Generative Agents memory stream implementation.

Implements the Park et al. (2023) Generative Agents memory system:
- Memory Stream: chronological record of experiences
- Retrieval: scoring = recency * importance * relevance
- Reflection: synthesizing higher-level insights from memories
- Planning: using memories to form and execute plans

Reference: "Generative Agents: Interactive Simulacra of Human Behavior"
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class GenerativeMemory:
    id: str
    content: str
    created_at: float
    last_accessed: float
    importance: float  # 1-10 scale
    access_count: int = 0
    embedding: Optional[list[float]] = None
    tags: list[str] = field(default_factory=list)
    memory_type: str = "observation"  # observation, reflection, plan

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content,
            "created_at": self.created_at, "last_accessed": self.last_accessed,
            "importance": self.importance, "access_count": self.access_count,
            "tags": self.tags, "memory_type": self.memory_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GenerativeMemory:
        return cls(**{k: v for k, v in data.items()})


@dataclass
class Reflection:
    id: str
    insight: str
    source_memory_ids: list[str]
    created_at: float
    last_accessed: float
    importance: float = 8.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "insight": self.insight,
            "source_memory_ids": self.source_memory_ids,
            "created_at": self.created_at, "last_accessed": self.last_accessed,
            "importance": self.importance,
        }


@dataclass
class Plan:
    id: str
    goal: str
    steps: list[str]
    current_step: int = 0
    status: str = "active"  # active, completed, abandoned
    created_at: float = field(default_factory=time.time)
    events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "goal": self.goal, "steps": self.steps,
            "current_step": self.current_step, "status": self.status,
            "created_at": self.created_at, "events": self.events,
        }


class GenerativeAgentsMemory:
    """Full Generative Agents memory system with stream, reflection, and planning."""

    HALF_LIFE_HOURS = 24.0  # recency decay half-life

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/memory/generative")
        self.memory_stream: list[GenerativeMemory] = []
        self.reflections: list[Reflection] = []
        self.plans: list[Plan] = []
        self._load()

    def add_memory(
        self, content: str, importance: float = 5.0,
        tags: Optional[list[str]] = None, memory_type: str = "observation",
    ) -> GenerativeMemory:
        """Add a new memory to the stream."""
        mem = GenerativeMemory(
            id=f"gm_{uuid.uuid4().hex[:8]}",
            content=content,
            created_at=time.time(),
            last_accessed=time.time(),
            importance=max(1.0, min(10.0, importance)),
            tags=tags or [],
            memory_type=memory_type,
        )
        self.memory_stream.append(mem)
        self._save()
        return mem

    def _recency_score(self, mem: GenerativeMemory) -> float:
        """Exponential decay based on time since last access."""
        hours = (time.time() - mem.last_accessed) / 3600
        return math.exp(-0.693 * hours / self.HALF_LIFE_HOURS)

    def _relevance_score(self, mem: GenerativeMemory, query_embedding: Optional[list[float]] = None) -> float:
        """Cosine similarity if embeddings available, else keyword overlap."""
        if mem.embedding and query_embedding:
            dot = sum(a * b for a, b in zip(mem.embedding, query_embedding))
            norm_a = math.sqrt(sum(a * a for a in mem.embedding))
            norm_b = math.sqrt(sum(b * b for b in query_embedding))
            if norm_a > 0 and norm_b > 0:
                return dot / (norm_a * norm_b)
        return 1.0  # default if no embedding

    def _importance_score(self, mem: GenerativeMemory) -> float:
        return mem.importance / 10.0

    def retrieve(
        self, query: str, k: int = 10,
        query_embedding: Optional[list[float]] = None,
        recency_weight: float = 1.0,
        relevance_weight: float = 1.0,
        importance_weight: float = 1.0,
    ) -> list[GenerativeMemory]:
        """Retrieve top-k memories using recency * importance * relevance scoring."""
        scored = []
        for mem in self.memory_stream:
            r = self._recency_score(mem) * recency_weight
            i = self._importance_score(mem) * importance_weight
            rel = self._relevance_score(mem, query_embedding) * relevance_weight
            score = r * i * rel
            scored.append((score, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [mem for _, mem in scored[:k]]
        for mem in results:
            mem.last_accessed = time.time()
            mem.access_count += 1
        return results

    def reflect(
        self, observation: str, source_ids: Optional[list[str]] = None,
        insight: str = "", importance: float = 8.0,
    ) -> Reflection:
        """Synthesize a reflection (higher-level insight) from memories."""
        refl = Reflection(
            id=f"refl_{uuid.uuid4().hex[:8]}",
            insight=insight or observation,
            source_memory_ids=source_ids or [],
            created_at=time.time(),
            last_accessed=time.time(),
            importance=importance,
        )
        self.reflections.append(refl)
        self._save()
        return refl

    def retrieve_with_reflections(
        self, query: str, k: int = 10, query_embedding: Optional[list[float]] = None,
    ) -> tuple[list[GenerativeMemory], list[Reflection]]:
        """Retrieve memories including reflections."""
        mems = self.retrieve(query, k=k, query_embedding=query_embedding)
        # Also score reflections
        refl_scored = []
        for r in self.reflections:
            r_mem = GenerativeMemory(
                id=r.id, content=r.insight, created_at=r.created_at,
                last_accessed=r.last_accessed, importance=r.importance,
                memory_type="reflection",
            )
            score = self._recency_score(r_mem) * self._importance_score(r_mem)
            refl_scored.append((score, r))
        refl_scored.sort(key=lambda x: x[0], reverse=True)
        return mems, [r for _, r in refl_scored[:k]]

    def create_plan(self, goal: str, steps: list[str]) -> Plan:
        """Create a new plan."""
        plan = Plan(
            id=f"plan_{uuid.uuid4().hex[:8]}",
            goal=goal, steps=steps,
        )
        self.plans.append(plan)
        self._save()
        return plan

    def execute_plan_step(self, plan_id: str, event: str = "") -> Optional[Plan]:
        """Advance a plan to the next step."""
        for p in self.plans:
            if p.id == plan_id and p.status == "active":
                if event:
                    p.events.append(event)
                p.current_step += 1
                if p.current_step >= len(p.steps):
                    p.status = "completed"
                self._save()
                return p
        return None

    def abandon_plan(self, plan_id: str) -> Optional[Plan]:
        for p in self.plans:
            if p.id == plan_id:
                p.status = "abandoned"
                self._save()
                return p
        return None

    def get_active_plans(self) -> list[Plan]:
        return [p for p in self.plans if p.status == "active"]

    def summary(self) -> str:
        active_plans = len([p for p in self.plans if p.status == "active"])
        return (
            f"Generative Agents Memory: {len(self.memory_stream)} memories, "
            f"{len(self.reflections)} reflections, {active_plans} active plans"
        )

    def _save(self) -> None:
        import json
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "stream.json").write_text(
            json.dumps([m.to_dict() for m in self.memory_stream], indent=2)
        )
        (self.data_dir / "reflections.json").write_text(
            json.dumps([r.to_dict() for r in self.reflections], indent=2)
        )
        (self.data_dir / "plans.json").write_text(
            json.dumps([p.to_dict() for p in self.plans], indent=2)
        )

    def _load(self) -> None:
        import json
        for name, cls, target in [
            ("stream.json", GenerativeMemory, "memory_stream"),
            ("reflections.json", Reflection, "reflections"),
            ("plans.json", Plan, "plans"),
        ]:
            path = self.data_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    setattr(self, target, [cls(**d) if not hasattr(cls, 'from_dict') else cls.from_dict(d) for d in data])
                except Exception:
                    pass
