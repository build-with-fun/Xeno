"""Mem0-style memory with A.U.D.N. cycle.

Implements the Mem0 memory management paradigm:
- ADD: Extract and store new memories from conversations
- UPDATE: Modify existing memories when contradictions found
- DELETE: Remove outdated or incorrect memories
- NOOP: Detect no-change scenarios (nothing to extract)

Reference: Mem0 (mem0ai) - https://github.com/mem0ai/mem0
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class MemoryAction(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    NOOP = "noop"


@dataclass
class Mem0Memory:
    id: str
    content: str
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    version: int = 1
    superseded_by: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content, "category": self.category,
            "metadata": self.metadata, "created_at": self.created_at,
            "updated_at": self.updated_at, "access_count": self.access_count,
            "last_accessed": self.last_accessed, "version": self.version,
            "superseded_by": self.superseded_by, "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Mem0Memory:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AuditEntry:
    action: str
    memory_id: str
    old_content: Optional[str]
    new_content: Optional[str]
    timestamp: float = field(default_factory=time.time)
    reason: str = ""


class Mem0Manager:
    """Mem0-style memory manager with A.U.D.N. lifecycle.

    Features:
    - Automatic memory extraction from conversations
    - Contradiction detection and update
    - Outdated memory cleanup
    - Deduplication
    - Audit trail
    - Version history
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/memory/mem0")
        self.memories: list[Mem0Memory] = []
        self.audit_log: list[AuditEntry] = []
        self._load()

    def add(
        self, content: str, category: str = "general",
        metadata: Optional[dict] = None,
    ) -> Mem0Memory:
        """ADD: Store a new memory, with deduplication check."""
        # Deduplication check
        existing = self._find_similar(content)
        if existing:
            # Update instead of adding duplicate
            return self.update(existing.id, content, reason="deduplication")

        mem = Mem0Memory(
            id=f"m0_{uuid.uuid4().hex[:8]}",
            content=content,
            category=category,
            metadata=metadata or {},
        )
        self.memories.append(mem)
        self.audit_log.append(AuditEntry(
            action="add", memory_id=mem.id,
            old_content=None, new_content=content,
        ))
        self._save()
        return mem

    def update(
        self, memory_id: str, new_content: str, reason: str = "correction",
    ) -> Mem0Memory:
        """UPDATE: Modify an existing memory, preserving version history."""
        for mem in self.memories:
            if mem.id == memory_id and mem.is_active:
                old_content = mem.content
                mem.content = new_content
                mem.version += 1
                mem.updated_at = time.time()
                self.audit_log.append(AuditEntry(
                    action="update", memory_id=mem.id,
                    old_content=old_content, new_content=new_content,
                    reason=reason,
                ))
                self._save()
                return mem
        return self.add(new_content, metadata={"update_reason": reason})

    def delete(self, memory_id: str, reason: str = "explicit") -> bool:
        """DELETE: Soft-delete a memory (marks inactive)."""
        for mem in self.memories:
            if mem.id == memory_id and mem.is_active:
                mem.is_active = False
                mem.superseded_by = None
                self.audit_log.append(AuditEntry(
                    action="delete", memory_id=mem.id,
                    old_content=mem.content, new_content=None, reason=reason,
                ))
                self._save()
                return True
        return False

    def noop(self, reason: str = "no_change_needed") -> None:
        """NOOP: Record that no memory action was needed."""
        self.audit_log.append(AuditEntry(
            action="noop", memory_id="",
            old_content=None, new_content=None, reason=reason,
        ))

    def search(self, query: str, category: Optional[str] = None, limit: int = 10) -> list[Mem0Memory]:
        """Search active memories."""
        query_words = set(query.lower().split())
        results = []
        for mem in self.memories:
            if not mem.is_active:
                continue
            if category and mem.category != category:
                continue
            content_words = set(mem.content.lower().split())
            overlap = len(query_words & content_words)
            age_factor = 1.0 / (1.0 + (time.time() - mem.last_accessed) / 86400)
            score = overlap * 0.7 + age_factor * 0.3
            results.append((score, mem))
        results.sort(key=lambda x: x[0], reverse=True)
        for _, mem in results[:limit]:
            mem.access_count += 1
            mem.last_accessed = time.time()
        return [mem for _, mem in results[:limit]]

    def get_all(self, include_inactive: bool = False) -> list[Mem0Memory]:
        if include_inactive:
            return list(self.memories)
        return [m for m in self.memories if m.is_active]

    def get_by_category(self, category: str) -> list[Mem0Memory]:
        return [m for m in self.memories if m.is_active and m.category == category]

    def _find_similar(self, content: str, threshold: float = 0.8) -> Optional[Mem0Memory]:
        """Find an existing memory with similar content."""
        words = set(content.lower().split())
        for mem in self.memories:
            if not mem.is_active:
                continue
            mem_words = set(mem.content.lower().split())
            if not words or not mem_words:
                continue
            intersection = len(words & mem_words)
            union = len(words | mem_words)
            jaccard = intersection / union if union > 0 else 0
            if jaccard > threshold:
                return mem
        return None

    def get_stats(self) -> dict[str, Any]:
        active = [m for m in self.memories if m.is_active]
        inactive = [m for m in self.memories if not m.is_active]
        actions = {}
        for entry in self.audit_log:
            actions[entry.action] = actions.get(entry.action, 0) + 1
        return {
            "total_memories": len(self.memories),
            "active": len(active),
            "inactive": len(inactive),
            "total_actions": len(self.audit_log),
            "action_breakdown": actions,
        }

    def summary(self) -> str:
        stats = self.get_stats()
        return (
            f"Mem0 Memory: {stats['active']} active / {stats['total_memories']} total, "
            f"{stats['total_actions']} actions logged"
        )

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "memories.json").write_text(
            json.dumps([m.to_dict() for m in self.memories], indent=2)
        )
        (self.data_dir / "audit.json").write_text(
            json.dumps([
                {"action": a.action, "memory_id": a.memory_id,
                 "old": a.old_content, "new": a.new_content,
                 "ts": a.timestamp, "reason": a.reason}
                for a in self.audit_log[-500:]
            ], indent=2)
        )

    def _load(self) -> None:
        mem_path = self.data_dir / "memories.json"
        if mem_path.exists():
            try:
                self.memories = [Mem0Memory.from_dict(d) for d in json.loads(mem_path.read_text())]
            except Exception:
                self.memories = []
        audit_path = self.data_dir / "audit.json"
        if audit_path.exists():
            try:
                data = json.loads(audit_path.read_text())
                self.audit_log = [
                    AuditEntry(action=d["action"], memory_id=d["memory_id"],
                               old_content=d.get("old"), new_content=d.get("new"),
                               timestamp=d.get("ts", 0), reason=d.get("reason", ""))
                    for d in data
                ]
            except Exception:
                self.audit_log = []
