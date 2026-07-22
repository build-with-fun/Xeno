"""Persistent thread state management.

Implements:
- Thread persistence across sessions (save/restore conversation threads)
- Thread metadata (title, tags, participants)
- Message history with timestamps
- Thread search and listing
- Checkpoint integration for thread snapshots
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ThreadMessage:
    id: str
    role: str  # user, assistant, system, tool
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "content": self.content,
            "timestamp": self.timestamp, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ThreadMessage:
        return cls(**{k: v for k, v in data.items()})


@dataclass
class Thread:
    id: str
    title: str = ""
    messages: list[ThreadMessage] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def last_message_time(self) -> float:
        return self.messages[-1].timestamp if self.messages else self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "tags": self.tags, "created_at": self.created_at,
            "updated_at": self.updated_at, "metadata": self.metadata,
            "is_active": self.is_active, "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Thread:
        messages = [ThreadMessage.from_dict(m) for m in data.get("messages", [])]
        d = {k: v for k, v in data.items() if k not in ("messages", "message_count")}
        return cls(messages=messages, **d)


class ThreadManager:
    """Persistent thread manager for conversation history.

    Features:
    - Create, list, search threads
    - Add messages to threads
    - Save/load threads to disk
    - Thread metadata (title, tags)
    - Export thread as markdown
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/threads")
        self.threads: dict[str, Thread] = {}
        self._load()

    def create_thread(self, title: str = "", tags: Optional[list[str]] = None) -> Thread:
        thread = Thread(
            id=f"thr_{uuid.uuid4().hex[:8]}",
            title=title or f"Thread {time.strftime('%Y-%m-%d %H:%M')}",
            tags=tags or [],
        )
        self.threads[thread.id] = thread
        self._save()
        return thread

    def get_thread(self, thread_id: str) -> Optional[Thread]:
        return self.threads.get(thread_id)

    def add_message(
        self, thread_id: str, role: str, content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[ThreadMessage]:
        thread = self.threads.get(thread_id)
        if not thread:
            return None
        msg = ThreadMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role=role, content=content, metadata=metadata or {},
        )
        thread.messages.append(msg)
        thread.updated_at = time.time()
        self._save()
        return msg

    def get_messages(self, thread_id: str, limit: Optional[int] = None) -> list[ThreadMessage]:
        thread = self.threads.get(thread_id)
        if not thread:
            return []
        if limit:
            return thread.messages[-limit:]
        return list(thread.messages)

    def list_threads(
        self, active_only: bool = True, tag: Optional[str] = None,
        limit: int = 50,
    ) -> list[Thread]:
        threads = list(self.threads.values())
        if active_only:
            threads = [t for t in threads if t.is_active]
        if tag:
            threads = [t for t in threads if tag in t.tags]
        threads.sort(key=lambda t: t.updated_at, reverse=True)
        return threads[:limit]

    def search_threads(self, query: str, limit: int = 10) -> list[Thread]:
        query_words = set(query.lower().split())
        results = []
        for thread in self.threads.values():
            title_words = set(thread.title.lower().split())
            msg_words = set()
            for msg in thread.messages[-10:]:
                msg_words.update(msg.content.lower().split())
            all_words = title_words | msg_words
            overlap = len(query_words & all_words)
            if overlap > 0:
                results.append((overlap, thread))
        results.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in results[:limit]]

    def close_thread(self, thread_id: str) -> bool:
        thread = self.threads.get(thread_id)
        if thread:
            thread.is_active = False
            self._save()
            return True
        return False

    def delete_thread(self, thread_id: str) -> bool:
        if thread_id in self.threads:
            del self.threads[thread_id]
            self._save()
            return True
        return False

    def export_thread(self, thread_id: str, format: str = "markdown") -> str:
        thread = self.threads.get(thread_id)
        if not thread:
            return ""
        if format == "markdown":
            lines = [f"# {thread.title}\n"]
            for msg in thread.messages:
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(msg.timestamp))
                lines.append(f"### [{msg.role}] {ts}\n")
                lines.append(f"{msg.content}\n")
            return "\n".join(lines)
        elif format == "json":
            return json.dumps(thread.to_dict(), indent=2)
        return ""

    def get_context_messages(self, thread_id: str, max_messages: int = 20) -> list[dict[str, str]]:
        """Get recent messages formatted for LLM context."""
        messages = self.get_messages(thread_id, limit=max_messages)
        return [{"role": m.role, "content": m.content} for m in messages]

    def summary(self) -> str:
        active = sum(1 for t in self.threads.values() if t.is_active)
        total_msgs = sum(t.message_count for t in self.threads.values())
        return f"Threads: {active} active / {len(self.threads)} total, {total_msgs} messages"

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "threads.json").write_text(
            json.dumps({tid: t.to_dict() for tid, t in self.threads.items()}, indent=2)
        )

    def _load(self) -> None:
        path = self.data_dir / "threads.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.threads = {k: Thread.from_dict(v) for k, v in data.items()}
            except Exception:
                self.threads = {}
