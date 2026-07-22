"""OS-style memory paging system (MemGPT/Letta pattern).

Implements virtual memory paging for agent context management:
- Main context (RAM): fast access, limited size
- Archival storage (disk): unlimited, slower access
- Recall storage: conversation history
- Page faults: trigger loading from archival to main
- LLM-driven memory management: the model decides what to page in/out

Reference: MemGPT/Letta - OS-inspired memory management for LLM agents
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class MemoryPage:
    id: str
    content: str
    page_type: str  # main, archival, recall
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    token_estimate: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content, "page_type": self.page_type,
            "priority": self.priority, "created_at": self.created_at,
            "last_accessed": self.last_accessed, "access_count": self.access_count,
            "token_estimate": self.token_estimate, "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryPage:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PageOperation:
    operation: str  # page_in, page_out, flush, compact
    page_id: str
    from_tier: str
    to_tier: str
    timestamp: float = field(default_factory=time.time)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "op": self.operation, "page": self.page_id,
            "from": self.from_tier, "to": self.to_tier,
            "ts": self.timestamp, "reason": self.reason,
        }


class OSPagingManager:
    """OS-inspired virtual memory paging for agent context.

    Three tiers:
    - main: Working context (like RAM) - limited by max_main_tokens
    - archival: Long-term storage (like disk) - unlimited
    - recall: Conversation history (like swap)

    Features:
    - Page in/out based on priority and access patterns
    - Token budget management
    - Automatic eviction when main memory is full
    - LLM-suggested page operations
    - Operation log for auditing
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        max_main_tokens: int = 8000,
        max_main_pages: int = 50,
    ):
        self.data_dir = data_dir or Path("data/memory/paging")
        self.max_main_tokens = max_main_tokens
        self.max_main_pages = max_main_pages
        self.pages: dict[str, MemoryPage] = {}
        self.operations: list[PageOperation] = []
        self._load()

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def page_in(
        self, content: str, tier: str = "main",
        priority: float = 0.5, tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> MemoryPage:
        """Add a new page to a tier."""
        page = MemoryPage(
            id=f"pg_{uuid.uuid4().hex[:8]}",
            content=content, page_type=tier,
            priority=priority, tags=tags or [],
            token_estimate=self._estimate_tokens(content),
            metadata=metadata or {},
        )
        self.pages[page.id] = page

        if tier == "main":
            self.operations.append(PageOperation(
                operation="page_in", page_id=page.id,
                from_tier="new", to_tier="main", reason="new page",
            ))
            self._evict_if_needed()

        self._save()
        return page

    def page_out(self, page_id: str, reason: str = "eviction") -> Optional[MemoryPage]:
        """Move a page from main to archival."""
        page = self.pages.get(page_id)
        if not page or page.page_type != "main":
            return None
        old_tier = page.page_type
        page.page_type = "archival"
        self.operations.append(PageOperation(
            operation="page_out", page_id=page.id,
            from_tier=old_tier, to_tier="archival", reason=reason,
        ))
        self._save()
        return page

    def page_in_from_archival(self, page_id: str, reason: str = "needed") -> Optional[MemoryPage]:
        """Load a page from archival back to main."""
        page = self.pages.get(page_id)
        if not page or page.page_type != "archival":
            return None
        page.page_type = "main"
        page.last_accessed = time.time()
        page.access_count += 1
        self.operations.append(PageOperation(
            operation="page_in", page_id=page.id,
            from_tier="archival", to_tier="main", reason=reason,
        ))
        self._evict_if_needed()
        self._save()
        return page

    def search_archival(self, query: str, limit: int = 10) -> list[MemoryPage]:
        """Search archival storage for relevant pages."""
        query_words = set(query.lower().split())
        results = []
        for page in self.pages.values():
            if page.page_type != "archival":
                continue
            content_words = set(page.content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                results.append((overlap, page))
        results.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in results[:limit]]

    def get_main_context(self) -> list[MemoryPage]:
        """Get all pages currently in main memory."""
        return [p for p in self.pages.values() if p.page_type == "main"]

    def get_main_tokens(self) -> int:
        return sum(p.token_estimate for p in self.pages.values() if p.page_type == "main")

    def get_archival_count(self) -> int:
        return sum(1 for p in self.pages.values() if p.page_type == "archival")

    def _evict_if_needed(self) -> None:
        """Evict lowest-priority pages from main when over budget."""
        main_pages = [p for p in self.pages.values() if p.page_type == "main"]
        # Evict by count
        while len(main_pages) > self.max_main_pages:
            weakest = min(main_pages, key=lambda p: (p.priority, p.last_accessed))
            self.page_out(weakest.id, reason="count_limit")
            main_pages.remove(weakest)
        # Evict by tokens
        while self.get_main_tokens() > self.max_main_tokens and main_pages:
            weakest = min(main_pages, key=lambda p: (p.priority, p.last_accessed))
            self.page_out(weakest.id, reason="token_limit")
            main_pages.remove(weakest)

    def compact(self) -> int:
        """Compact archival storage (remove low-priority pages)."""
        removed = 0
        archival = [p for p in self.pages.values() if p.page_type == "archival"]
        for page in sorted(archival, key=lambda p: p.priority):
            if page.priority < 0.2:
                del self.pages[page.id]
                removed += 1
        if removed:
            self._save()
        return removed

    def get_stats(self) -> dict[str, Any]:
        main = [p for p in self.pages.values() if p.page_type == "main"]
        archival = [p for p in self.pages.values() if p.page_type == "archival"]
        return {
            "main_pages": len(main),
            "main_tokens": sum(p.token_estimate for p in main),
            "max_main_tokens": self.max_main_tokens,
            "archival_pages": len(archival),
            "total_operations": len(self.operations),
        }

    def summary(self) -> str:
        s = self.get_stats()
        return (
            f"OS Paging: {s['main_pages']} main pages ({s['main_tokens']}/{s['max_main_tokens']} tokens), "
            f"{s['archival_pages']} archival pages, {s['total_operations']} operations"
        )

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "pages.json").write_text(
            json.dumps({pid: p.to_dict() for pid, p in self.pages.items()}, indent=2)
        )
        (self.data_dir / "operations.json").write_text(
            json.dumps([op.to_dict() for op in self.operations[-500:]], indent=2)
        )

    def _load(self) -> None:
        pages_path = self.data_dir / "pages.json"
        if pages_path.exists():
            try:
                data = json.loads(pages_path.read_text())
                self.pages = {k: MemoryPage.from_dict(v) for k, v in data.items()}
            except Exception:
                self.pages = {}
        ops_path = self.data_dir / "operations.json"
        if ops_path.exists():
            try:
                data = json.loads(ops_path.read_text())
                self.operations = [
                    PageOperation(operation=d["op"], page_id=d["page"],
                                  from_tier=d["from"], to_tier=d["to"],
                                  timestamp=d.get("ts", 0), reason=d.get("reason", ""))
                    for d in data
                ]
            except Exception:
                self.operations = []
