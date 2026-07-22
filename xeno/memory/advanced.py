"""Four-tier memory architecture for Xeno.

Following the deepagents guide's taxonomy:
- Working Memory: Current conversation context (like CPU registers)
- Episodic Memory: Past experiences and interactions (like RAM)
- Semantic Memory: Facts, knowledge, relationships (like disk)
- Procedural Memory: Skills, procedures, how-to knowledge (like program memory)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryEntry:
    id: str
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    decay_rate: float = 0.01
    tags: list[str] = field(default_factory=list)
    source: str = ""
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
            "decay_rate": self.decay_rate,
            "tags": self.tags,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", time.time()),
            created_at=data.get("created_at", time.time()),
            decay_rate=data.get("decay_rate", 0.01),
            tags=data.get("tags", []),
            source=data.get("source", ""),
        )

    def strength(self) -> float:
        """Calculate current memory strength (decays over time, boosts on access)."""
        age = time.time() - self.last_accessed
        decay = self.decay_rate * age / 3600  # per hour
        access_boost = min(self.access_count * 0.05, 0.5)
        return max(0.0, min(1.0, self.importance - decay + access_boost))

    def touch(self) -> None:
        """Record an access to this memory."""
        self.access_count += 1
        self.last_accessed = time.time()


class WorkingMemory:
    """Short-term working memory (conversation context window).

    Like human working memory: limited capacity, fast access.
    Stores the current conversation and immediate context.
    """

    def __init__(self, max_items: int = 50, max_tokens: int = 8000):
        self.max_items = max_items
        self.max_tokens = max_tokens
        self.items: list[MemoryEntry] = []
        self._buffer: list[dict[str, str]] = []

    def add(self, content: str, role: str = "user", metadata: Optional[dict] = None) -> MemoryEntry:
        """Add to working memory."""
        entry = MemoryEntry(
            id=f"wm_{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.WORKING,
            content=content,
            metadata={"role": role, **(metadata or {})},
            importance=0.8,
            decay_rate=0.5,  # Fast decay for working memory
        )
        self.items.append(entry)
        self._buffer.append({"role": role, "content": content})
        self._evict()
        return entry

    def get_context(self) -> list[dict[str, str]]:
        """Get current working memory as conversation context."""
        return list(self._buffer)

    def clear(self) -> None:
        """Clear working memory (context switch)."""
        self.items.clear()
        self._buffer.clear()

    def summary(self) -> str:
        """Summarize current working memory contents."""
        if not self.items:
            return "Working memory is empty."
        return f"Working memory: {len(self.items)} items, {len(self._buffer)} messages"

    def _evict(self) -> None:
        """Evict oldest/lowest-importance items when over capacity."""
        while len(self.items) > self.max_items:
            weakest = min(self.items, key=lambda e: e.strength())
            self.items.remove(weakest)
            self._buffer = [
                msg for msg in self._buffer
                if msg["content"] != weakest.content
            ]


class EpisodicMemory:
    """Medium-term episodic memory (past experiences).

    Stores specific interactions, events, and experiences.
    Supports temporal queries and experience replay.
    """

    def __init__(self, storage_path: Optional[Path] = None, max_entries: int = 1000):
        self.storage_path = storage_path
        self.max_entries = max_entries
        self.episodes: list[MemoryEntry] = []
        if storage_path and storage_path.exists():
            self._load()

    def record(
        self,
        content: str,
        event_type: str = "interaction",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> MemoryEntry:
        """Record an episode/experience."""
        entry = MemoryEntry(
            id=f"ep_{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.EPISODIC,
            content=content,
            metadata={"event_type": event_type, **(metadata or {})},
            importance=importance,
            decay_rate=0.005,  # Slower decay
            tags=tags or [],
        )
        self.episodes.append(entry)
        self._evict()
        self._save()
        return entry

    def recall(
        self,
        query: str = "",
        event_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
        min_strength: float = 0.1,
    ) -> list[MemoryEntry]:
        """Recall episodes matching criteria."""
        candidates = []
        for ep in self.episodes:
            if ep.strength() < min_strength:
                continue
            if event_type and ep.metadata.get("event_type") != event_type:
                continue
            if tags and not any(t in ep.tags for t in tags):
                continue
            if query:
                query_words = set(query.lower().split())
                content_words = set(ep.content.lower().split())
                overlap = len(query_words & content_words)
                score = ep.strength() * (1 + overlap * 0.2)
            else:
                score = ep.strength()
            candidates.append((score, ep))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in candidates[:limit]]

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent episodes."""
        return self.episodes[-limit:]

    def get_timeline(self, start_time: float, end_time: float) -> list[MemoryEntry]:
        """Get episodes in a time range."""
        return [
            ep for ep in self.episodes
            if start_time <= ep.created_at <= end_time
        ]

    def summary(self) -> str:
        return f"Episodic memory: {len(self.episodes)} episodes"

    def _evict(self) -> None:
        while len(self.episodes) > self.max_entries:
            weakest = min(self.episodes, key=lambda e: e.strength())
            self.episodes.remove(weakest)

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [ep.to_dict() for ep in self.episodes]
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        try:
            data = json.loads(self.storage_path.read_text())
            self.episodes = [MemoryEntry.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            self.episodes = []


class SemanticMemory:
    """Long-term semantic memory (facts and knowledge).

    Stores facts, entity relationships, and structured knowledge.
    Uses ChromaDB for vector similarity search when available.
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        collection_name: str = "xeno_semantic",
    ):
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.entries: list[MemoryEntry] = []
        self._chroma_collection = None
        self._chroma_client = None

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

        self._init_chroma()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB with Ollama embeddings."""
        try:
            import chromadb
            from xeno.memory.ollama_embed import get_embedding_function
            ef = get_embedding_function()
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.storage_path / "chroma") if self.storage_path else None
            )
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=ef,
            )
        except ImportError:
            self._chroma_collection = None

    def store(
        self,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> MemoryEntry:
        """Store a fact or piece of knowledge."""
        entry = MemoryEntry(
            id=f"sm_{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.SEMANTIC,
            content=content,
            metadata={"category": category, **(metadata or {})},
            importance=importance,
            decay_rate=0.001,  # Very slow decay for semantic memory
            tags=tags or [],
            embedding=embedding,
        )
        self.entries.append(entry)

        if self._chroma_collection:
            meta = {"category": category, "importance": importance}
            if tags:
                meta["tags"] = ",".join(tags)
            self._chroma_collection.add(
                ids=[entry.id],
                documents=[content],
                metadatas=[meta],
            )
        self._save()
        return entry

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        min_strength: float = 0.1,
    ) -> list[MemoryEntry]:
        """Search semantic memory."""
        if self._chroma_collection:
            try:
                where = {"category": category} if category else None
                results = self._chroma_collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where,
                )
                ids = results["ids"][0] if results["ids"] else []
                return [self._get_by_id(i) for i in ids if self._get_by_id(i)]
            except Exception:
                pass

        # Fallback: keyword search
        results = []
        query_words = set(query.lower().split())
        for entry in self.entries:
            if entry.strength() < min_strength:
                continue
            if category and entry.metadata.get("category") != category:
                continue
            content_words = set(entry.content.lower().split())
            overlap = len(query_words & content_words)
            score = entry.strength() * (1 + overlap * 0.3)
            results.append((score, entry))
        results.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in results[:limit]]

    def get_by_category(self, category: str) -> list[MemoryEntry]:
        """Get all entries in a category."""
        return [e for e in self.entries if e.metadata.get("category") == category]

    def get_by_tag(self, tag: str) -> list[MemoryEntry]:
        """Get all entries with a specific tag."""
        return [e for e in self.entries if tag in e.tags]

    def _get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        for e in self.entries:
            if e.id == entry_id:
                e.touch()
                return e
        return None

    def summary(self) -> str:
        categories = {}
        for e in self.entries:
            cat = e.metadata.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        cat_str = ", ".join(f"{k}: {v}" for k, v in categories.items())
        return f"Semantic memory: {len(self.entries)} entries ({cat_str})"

    def _save(self) -> None:
        if not self.storage_path:
            return
        data = [e.to_dict() for e in self.entries]
        (self.storage_path / "semantic.json").write_text(json.dumps(data, indent=2))

    def load_from_file(self) -> None:
        if not self.storage_path:
            return
        path = self.storage_path / "semantic.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.entries = [MemoryEntry.from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError):
                self.entries = []


class ProceduralMemory:
    """Long-term procedural memory (skills and procedures).

    Stores how to do things: skills, workflows, procedures, code patterns.
    This is the "skill library" from the deepagents guide.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self.procedures: list[MemoryEntry] = []
        if storage_path and storage_path.exists():
            self._load()

    def store_skill(
        self,
        name: str,
        instructions: str,
        category: str = "general",
        prerequisites: Optional[list[str]] = None,
        examples: Optional[list[str]] = None,
    ) -> MemoryEntry:
        """Store a skill or procedure."""
        entry = MemoryEntry(
            id=f"pm_{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.PROCEDURAL,
            content=instructions,
            metadata={
                "skill_name": name,
                "category": category,
                "prerequisites": prerequisites or [],
                "examples": examples or [],
            },
            importance=0.7,
            decay_rate=0.002,
            tags=[name, category],
        )
        self.procedures.append(entry)
        self._save()
        return entry

    def get_skill(self, name: str) -> Optional[MemoryEntry]:
        """Get a skill by name."""
        for proc in self.procedures:
            if proc.metadata.get("skill_name") == name:
                proc.touch()
                return proc
        return None

    def search_skills(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Search for relevant skills."""
        results = []
        query_words = set(query.lower().split())
        for proc in self.procedures:
            if category and proc.metadata.get("category") != category:
                continue
            name_words = set(proc.metadata.get("skill_name", "").lower().split())
            content_words = set(proc.content.lower().split())
            overlap = len(query_words & (name_words | content_words))
            score = proc.strength() * (1 + overlap * 0.3)
            results.append((score, proc))
        results.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in results[:limit]]

    def get_all_skills(self) -> list[dict[str, str]]:
        """List all stored skills."""
        return [
            {
                "name": p.metadata.get("skill_name", "unknown"),
                "category": p.metadata.get("category", "general"),
                "content_preview": p.content[:100],
            }
            for p in self.procedures
        ]

    def summary(self) -> str:
        return f"Procedural memory: {len(self.procedures)} skills"

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.mkdir(parents=True, exist_ok=True)
        data = [p.to_dict() for p in self.procedures]
        (self.storage_path / "procedural.json").write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        path = self.storage_path / "procedural.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.procedures = [MemoryEntry.from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError):
                self.procedures = []


class AdvancedMemoryManager:
    """Unified 4-tier memory system.

    Coordinates working, episodic, semantic, and procedural memory.
    Implements memory consolidation (moving important working memories to long-term).
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/memory")

        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(self.data_dir / "episodic.json")
        self.semantic = SemanticMemory(self.data_dir / "semantic", "xeno_semantic")
        self.procedural = ProceduralMemory(self.data_dir / "procedural")
        self.semantic.load_from_file()

    def remember(self, content: str, role: str = "user", **kwargs) -> MemoryEntry:
        """Add to working memory."""
        return self.working.add(content, role, kwargs)

    def record_experience(
        self,
        content: str,
        event_type: str = "interaction",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
    ) -> MemoryEntry:
        """Record an experience to episodic memory."""
        return self.episodic.record(content, event_type, importance, tags)

    def remember_fact(
        self,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
    ) -> MemoryEntry:
        """Store a fact in semantic memory."""
        return self.semantic.store(content, category, importance, tags)

    def remember_skill(
        self,
        name: str,
        instructions: str,
        category: str = "general",
    ) -> MemoryEntry:
        """Store a skill in procedural memory."""
        return self.procedural.store_skill(name, instructions, category)

    def recall(self, query: str, memory_type: Optional[MemoryType] = None, limit: int = 10) -> dict[str, list]:
        """Recall from all memory types."""
        results = {}
        if memory_type is None or memory_type == MemoryType.EPISODIC:
            results["episodic"] = self.episodic.recall(query, limit=limit)
        if memory_type is None or memory_type == MemoryType.SEMANTIC:
            results["semantic"] = self.semantic.search(query, limit=limit)
        if memory_type is None or memory_type == MemoryType.PROCEDURAL:
            results["procedural"] = self.procedural.search_skills(query, limit=limit)
        return results

    def get_context_window(self) -> list[dict[str, str]]:
        """Get the current working context for the agent."""
        return self.working.get_context()

    def consolidate(self, max_working: int = 20) -> None:
        """Consolidate: move important working memories to long-term.

        This mimics the brain's memory consolidation during sleep.
        """
        if len(self.working.items) <= max_working:
            return

        items_by_strength = sorted(
            self.working.items,
            key=lambda e: e.strength(),
            reverse=True,
        )

        for item in items_by_strength[max_working:]:
            if item.strength() > 0.6:
                self.episodic.record(
                    content=item.content,
                    event_type="consolidated",
                    importance=item.importance,
                )

    def full_summary(self) -> str:
        """Get a full summary of all memory systems."""
        return (
            f"Memory System Status:\n"
            f"  {self.working.summary()}\n"
            f"  {self.episodic.summary()}\n"
            f"  {self.semantic.summary()}\n"
            f"  {self.procedural.summary()}"
        )
