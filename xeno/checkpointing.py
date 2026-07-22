"""Checkpointing and state persistence for Xeno.

Implements LangGraph-style checkpointing for conversation state persistence.
Supports save, restore, fork, and list operations.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Checkpoint:
    """A conversation state checkpoint."""
    id: str
    thread_id: str
    state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    parent_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)


class CheckpointManager:
    """Manages conversation state checkpoints.

    Provides save/restore/fork for conversation state, enabling:
    - Conversation persistence across sessions
    - State rollback on errors
    - Branching conversations (fork)
    - Multi-session management
    """

    def __init__(self, storage_dir: Optional[Path] = None, max_checkpoints: int = 50):
        self.storage_dir = storage_dir or Path("data/checkpoints")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, Checkpoint] = {}
        self._load_all()

    def save(
        self,
        thread_id: str,
        state: dict[str, Any],
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        parent_id: Optional[str] = None,
    ) -> Checkpoint:
        """Save a checkpoint."""
        cp_id = f"cp_{uuid.uuid4().hex[:12]}"
        checkpoint = Checkpoint(
            id=cp_id,
            thread_id=thread_id,
            state=state,
            metadata=metadata or {},
            parent_id=parent_id,
            tags=tags or [],
        )
        self._checkpoints[cp_id] = checkpoint
        self._persist(checkpoint)
        self._evict(thread_id)
        return checkpoint

    def restore(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Restore a checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    def fork(self, checkpoint_id: str, new_state: Optional[dict] = None) -> Optional[Checkpoint]:
        """Fork from an existing checkpoint."""
        parent = self._checkpoints.get(checkpoint_id)
        if not parent:
            return None
        state = new_state if new_state is not None else dict(parent.state)
        return self.save(
            thread_id=parent.thread_id,
            state=state,
            metadata={**parent.metadata, "forked_from": checkpoint_id},
            parent_id=checkpoint_id,
        )

    def get_latest(self, thread_id: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a thread."""
        thread_cps = [
            cp for cp in self._checkpoints.values()
            if cp.thread_id == thread_id
        ]
        if not thread_cps:
            return None
        return max(thread_cps, key=lambda cp: cp.created_at)

    def list_checkpoints(
        self,
        thread_id: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> list[Checkpoint]:
        """List checkpoints with optional filters."""
        results = list(self._checkpoints.values())
        if thread_id:
            results = [cp for cp in results if cp.thread_id == thread_id]
        if tag:
            results = [cp for cp in results if tag in cp.tags]
        results.sort(key=lambda cp: cp.created_at, reverse=True)
        return results[:limit]

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        cp = self._checkpoints.pop(checkpoint_id, None)
        if cp:
            path = self.storage_dir / f"{checkpoint_id}.json"
            path.unlink(missing_ok=True)
            return True
        return False

    def get_thread_history(self, thread_id: str) -> list[Checkpoint]:
        """Get the full history of a thread as ordered checkpoints."""
        thread_cps = [
            cp for cp in self._checkpoints.values()
            if cp.thread_id == thread_id
        ]
        thread_cps.sort(key=lambda cp: cp.created_at)
        return thread_cps

    def _persist(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint to disk."""
        path = self.storage_dir / f"{checkpoint.id}.json"
        data = {
            "id": checkpoint.id,
            "thread_id": checkpoint.thread_id,
            "state": checkpoint.state,
            "metadata": checkpoint.metadata,
            "created_at": checkpoint.created_at,
            "parent_id": checkpoint.parent_id,
            "tags": checkpoint.tags,
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    def _load_all(self) -> None:
        """Load all checkpoints from disk."""
        for path in self.storage_dir.glob("cp_*.json"):
            try:
                data = json.loads(path.read_text())
                cp = Checkpoint(
                    id=data["id"],
                    thread_id=data["thread_id"],
                    state=data["state"],
                    metadata=data.get("metadata", {}),
                    created_at=data.get("created_at", 0),
                    parent_id=data.get("parent_id"),
                    tags=data.get("tags", []),
                )
                self._checkpoints[cp.id] = cp
            except (json.JSONDecodeError, KeyError):
                continue

    def _evict(self, thread_id: str) -> None:
        """Evict old checkpoints for a thread."""
        thread_cps = sorted(
            [cp for cp in self._checkpoints.values() if cp.thread_id == thread_id],
            key=lambda cp: cp.created_at,
        )
        while len(thread_cps) > self.max_checkpoints:
            oldest = thread_cps.pop(0)
            self.delete(oldest.id)
