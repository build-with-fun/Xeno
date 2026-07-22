"""Temporal Knowledge Graph — Graphiti-style memory with fact versioning.

Facts are stored as (subject, predicate, object) triples with explicit
valid_from / valid_to timestamps. Supports:
- Temporal queries: "what was true in March?"
- Contradiction detection: overlapping facts with different values
- Entity resolution: merging duplicate entities
- Context export: natural language summary for prompt injection
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

INF = float("inf")


@dataclass
class TemporalFact:
    id: str
    subject: str
    predicate: str
    object: str
    valid_from: float
    valid_to: float = INF
    confidence: float = 1.0
    source: str = ""
    superseded_by: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def is_valid_at(self, timestamp: float) -> bool:
        return self.valid_from <= timestamp <= self.valid_to

    def is_current(self) -> bool:
        return self.is_valid_at(time.time())

    def to_dict(self) -> dict:
        return {
            "id": self.id, "subject": self.subject, "predicate": self.predicate,
            "object": self.object, "valid_from": self.valid_from, "valid_to": self.valid_to,
            "confidence": self.confidence, "source": self.source,
            "superseded_by": self.superseded_by, "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TemporalFact:
        return cls(**data)


class TemporalKnowledgeGraph:
    """Temporal knowledge graph with fact versioning and contradiction resolution."""

    def __init__(self, storage_path: Optional[Path] = None, namespace: str = "default"):
        self.storage_path = storage_path
        self.namespace = namespace
        self.facts: dict[str, TemporalFact] = {}
        self._index_subject: dict[str, set[str]] = {}
        if storage_path:
            self._load()

    # ── Add / Update / Delete ─────────────────────────────────────────────

    def add_fact(self, subject: str, predicate: str, object: str,
                 confidence: float = 1.0, source: str = "",
                 valid_from: Optional[float] = None,
                 valid_to: Optional[float] = None,
                 metadata: Optional[dict] = None) -> TemporalFact:
        """Add a fact. Automatically detects and resolves contradictions."""
        now = valid_from or time.time()

        existing = self._find_current(subject, predicate)
        if existing:
            existing.valid_to = now
            existing.superseded_by = None

        fact = TemporalFact(
            id=f"tf_{uuid.uuid4().hex[:12]}",
            subject=subject, predicate=predicate, object=object,
            valid_from=now, valid_to=valid_to or INF,
            confidence=confidence, source=source,
            metadata=metadata or {},
        )
        self.facts[fact.id] = fact
        self._index_subject.setdefault(subject, set()).add(fact.id)

        contradiction = self._detect_contradiction(fact)
        if contradiction:
            self._resolve_contradiction(fact, contradiction)

        self._save()
        return fact

    def update_fact(self, fact_id: str, new_object: str, confidence: float = 1.0) -> Optional[TemporalFact]:
        """Update a fact by superseding it."""
        old = self.facts.get(fact_id)
        if not old:
            return None
        now = time.time()
        old.valid_to = now
        new_fact = self.add_fact(old.subject, old.predicate, new_object,
                                 confidence=confidence, source=f"update:{fact_id}")
        old.superseded_by = new_fact.id
        self._save()
        return new_fact

    def retract(self, fact_id: str) -> bool:
        """Retract a fact (mark as invalid)."""
        fact = self.facts.get(fact_id)
        if not fact:
            return False
        fact.valid_to = time.time()
        self._save()
        return True

    # ── Query ─────────────────────────────────────────────────────────────

    def query(self, subject: str, predicate: str = "",
              as_of: Optional[float] = None, current_only: bool = True) -> list[TemporalFact]:
        """Query facts by subject and optionally predicate."""
        now = as_of or time.time()
        results = []
        fact_ids = self._index_subject.get(subject, set())
        for fid in fact_ids:
            fact = self.facts.get(fid)
            if not fact:
                continue
            if predicate and fact.predicate != predicate:
                continue
            if current_only and not fact.is_valid_at(now):
                continue
            results.append(fact)
        results.sort(key=lambda f: f.valid_from, reverse=True)
        return results

    def get_current(self, subject: str, predicate: str) -> Optional[str]:
        """Get the current value of a fact. Returns None if not found."""
        facts = self.query(subject, predicate, current_only=True)
        return facts[0].object if facts else None

    def get_history(self, subject: str, predicate: str) -> list[TemporalFact]:
        """Get all historical versions of a fact (including superseded)."""
        results = []
        for fact in self.facts.values():
            if fact.subject == subject and fact.predicate == predicate:
                results.append(fact)
        results.sort(key=lambda f: f.valid_from)
        return results

    def query_by_object(self, obj: str, current_only: bool = True) -> list[TemporalFact]:
        """Find facts by object value."""
        now = time.time()
        results = []
        for fact in self.facts.values():
            if fact.object == obj:
                if current_only and not fact.is_valid_at(now):
                    continue
                results.append(fact)
        return results

    def search(self, query: str, limit: int = 10) -> list[TemporalFact]:
        """Search all facts by keyword match on subject/predicate/object."""
        q = query.lower()
        results = []
        for fact in self.facts.values():
            if not fact.is_current():
                continue
            if q in fact.subject.lower() or q in fact.predicate.lower() or q in fact.object.lower():
                results.append(fact)
        results.sort(key=lambda f: f.confidence, reverse=True)
        return results[:limit]

    def get_all_facts(self, namespace: str = "") -> list[TemporalFact]:
        """Get all current facts, optionally filtered by namespace metadata."""
        return [f for f in self.facts.values() if f.is_current() and
                (not namespace or f.metadata.get("namespace") == namespace or f.metadata.get("agent") == namespace)]

    # ── Context Export ────────────────────────────────────────────────────

    def export_context(self, subjects: Optional[list[str]] = None, limit: int = 30) -> str:
        """Generate a natural language summary of current facts for prompt injection."""
        facts = [f for f in self.facts.values() if f.is_current()]
        if subjects:
            facts = [f for f in facts if f.subject in subjects]
        facts.sort(key=lambda f: f.confidence, reverse=True)

        lines = [f"--- Temporal Knowledge ({self.namespace}) ---"]
        added = 0
        seen_relations = set()
        for fact in facts[:limit]:
            key = (fact.subject, fact.predicate)
            if key in seen_relations:
                continue
            seen_relations.add(key)
            source = f"[{fact.source}]" if fact.source else ""
            lines.append(f"  • {fact.subject} {fact.predicate} {fact.object} {source}")
            added += 1

        if added == 0:
            return ""
        return "\n".join(lines)

    def get_entity_summary(self, subject: str) -> str:
        """Get all known facts about an entity."""
        facts = self.query(subject)
        if not facts:
            return f"No facts known about '{subject}'"
        lines = [f"Known facts about {subject}:"]
        for f in facts:
            lines.append(f"  • {f.predicate}: {f.object}")
        return "\n".join(lines)

    # ── Contradiction Detection & Resolution ──────────────────────────────

    def _find_current(self, subject: str, predicate: str) -> Optional[TemporalFact]:
        """Find the currently valid fact for (subject, predicate)."""
        now = time.time()
        for fact in self.facts.values():
            if fact.subject == subject and fact.predicate == predicate and fact.is_valid_at(now):
                return fact
        return None

    def _detect_contradiction(self, new_fact: TemporalFact) -> Optional[TemporalFact]:
        """Detect if a fact contradicts an existing one."""
        for fact in self.facts.values():
            if fact.id == new_fact.id:
                continue
            if fact.subject == new_fact.subject and fact.predicate == new_fact.predicate:
                if fact.is_valid_at(new_fact.valid_from) and fact.object != new_fact.object:
                    return fact
        return None

    def _resolve_contradiction(self, new_fact: TemporalFact, existing: TemporalFact):
        """Resolve contradiction by closing the existing fact's validity."""
        if new_fact.confidence >= existing.confidence:
            existing.valid_to = new_fact.valid_from
            existing.superseded_by = new_fact.id
            logger.info(f"Resolved contradiction: '{existing.object}' → '{new_fact.object}' for {existing.subject}.{existing.predicate}")
        else:
            new_fact.valid_to = existing.valid_from
            logger.info(f"New fact rejected (lower confidence): {new_fact.object}")

    # ── Persistence ───────────────────────────────────────────────────────

    def _get_file_path(self) -> Path:
        if self.storage_path:
            return self.storage_path / f"temporal_{self.namespace}.json"
        return Path(f"data/memory/temporal_{self.namespace}.json")

    def _save(self):
        path = self._get_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "namespace": self.namespace,
            "facts": [f.to_dict() for f in self.facts.values()],
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    def _load(self):
        path = self._get_file_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for d in data.get("facts", []):
                    fact = TemporalFact.from_dict(d)
                    self.facts[fact.id] = fact
                    self._index_subject.setdefault(fact.subject, set()).add(fact.id)
            except Exception as e:
                logger.warning(f"Failed to load temporal KG '{self.namespace}': {e}")

    def clear(self):
        self.facts.clear()
        self._index_subject.clear()
        self._save()

    def stats(self) -> dict:
        current = sum(1 for f in self.facts.values() if f.is_current())
        return {"total_facts": len(self.facts), "current_facts": current,
                "namespace": self.namespace, "entities": len(self._index_subject)}


# Global registry of temporal KGs (one per namespace)
_KG_REGISTRY: dict[str, TemporalKnowledgeGraph] = {}


def get_temporal_kg(namespace: str = "default",
                    storage_path: Optional[Path] = None) -> TemporalKnowledgeGraph:
    """Get or create a temporal KG for a namespace."""
    if namespace not in _KG_REGISTRY:
        _KG_REGISTRY[namespace] = TemporalKnowledgeGraph(storage_path, namespace)
    return _KG_REGISTRY[namespace]


def get_all_temporal_kgs() -> dict[str, TemporalKnowledgeGraph]:
    return dict(_KG_REGISTRY)
