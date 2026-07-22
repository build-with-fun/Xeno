"""Thread-safe dedup tracker for message IDs.

Fixes the original code's issues:
- `_seen_message_ids` (a `set`) was mutated from daemon threads with NO lock
- Persistence happened in a fire-and-forget thread, racing with reads
- In-memory set grew unbounded (only the on-disk file was trimmed)
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.memory.store import store

logger = get_logger(__name__)

# LRU cap: keep last 10k seen IDs in memory (~1MB)
_MAX_IN_MEMORY = 10_000
_TTL_HOURS = 48


class SeenTracker:
    """Thread-safe dedup tracker with TTL and disk persistence."""

    def __init__(self, max_in_memory: int = _MAX_IN_MEMORY, ttl_hours: int = _TTL_HOURS):
        self._lock = threading.RLock()
        self._ids: OrderedDict[str, datetime] = OrderedDict()
        self._max = max_in_memory
        self._ttl = timedelta(hours=ttl_hours)
        self._dirty = False
        self._last_save = datetime.now()

    def load(self) -> None:
        """Load seen IDs from disk, dropping expired entries."""
        data = store.read_raw(_SEEN_IDS_PATH, {}) or {}
        cutoff = datetime.now() - self._ttl
        loaded = 0
        with self._lock:
            for msg_id, ts_str in data.items():
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    continue
                if ts < cutoff:
                    continue
                self._ids[msg_id] = ts
                loaded += 1
            # Re-order by timestamp (oldest first for LRU eviction)
            self._ids = OrderedDict(sorted(self._ids.items(), key=lambda kv: kv[1]))
        logger.info(f"[SeenIDs] Loaded {loaded} IDs from disk")

    def is_duplicate(self, msg_id: str) -> bool:
        """Return True if msg_id has been seen recently."""
        if not msg_id:
            return False
        with self._lock:
            ts = self._ids.get(msg_id)
            if ts is None:
                return False
            if datetime.now() - ts > self._ttl:
                # Expired — treat as not seen
                self._ids.pop(msg_id, None)
                return False
            # Move to end (most recently seen)
            self._ids.move_to_end(msg_id)
            return True

    def mark_seen(self, msg_id: str) -> None:
        """Record msg_id as seen. Persists to disk asynchronously."""
        if not msg_id:
            return
        now = datetime.now()
        with self._lock:
            self._ids[msg_id] = now
            self._ids.move_to_end(msg_id)
            # LRU eviction
            while len(self._ids) > self._max:
                self._ids.popitem(last=False)
            self._dirty = True
            # Throttle disk writes to once per 5 seconds
            if (now - self._last_save).total_seconds() >= 5:
                self._persist_locked()

    def flush(self) -> None:
        """Force-persist to disk. Called on shutdown."""
        with self._lock:
            self._persist_locked()

    def _persist_locked(self) -> None:
        """Persist current state to disk. Caller must hold _lock."""
        if not self._dirty:
            return
        cutoff = datetime.now() - self._ttl
        data = {k: v.isoformat() for k, v in self._ids.items() if v >= cutoff}
        try:
            store.write_raw(_SEEN_IDS_PATH, data)
            self._dirty = False
            self._last_save = datetime.now()
        except Exception as e:
            logger.warning(f"[SeenIDs] Persist failed: {e}")

    def stats(self) -> dict:
        with self._lock:
            return {
                "in_memory_count": len(self._ids),
                "ttl_hours": self._ttl.total_seconds() / 3600,
                "max_in_memory": self._max,
                "dirty": self._dirty,
            }


# Path: data/seen_ids.json
from media.whatsapp.config import settings
_SEEN_IDS_PATH = settings.seen_ids_path


# Singleton
seen_tracker = SeenTracker()
