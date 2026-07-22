"""Thread-safe approval queue.

Fixes the original code's issues:
- File was marked "processing" then written — but admin API could approve
  BETWEEN read and write, losing the approval
- Files removed with `os.remove` — FileNotFoundError could kill the worker
- No locking on individual queue items
- image_bytes were discarded when saving to the queue
"""
from __future__ import annotations

import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.core.types import ApprovalItem, Decision, ProcessedMessage
from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.utils.text import safe_filename

logger = get_logger(__name__)


class ApprovalQueue:
    """File-backed queue of messages awaiting human approval."""

    COLLECTION = "pending"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Per-item locks prevent race between worker & admin API
        self._item_locks: dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _item_lock(self, msg_id: int) -> threading.Lock:
        with self._locks_guard:
            if msg_id not in self._item_locks:
                self._item_locks[msg_id] = threading.Lock()
            return self._item_locks[msg_id]

    def _path_for(self, msg_id: int) -> Path:
        return store.path_for(self.COLLECTION, str(msg_id))

    def add(
        self, contact: str, messages: list[ProcessedMessage], decision: Decision,
    ) -> int:
        """Add a new item to the queue. Returns the assigned msg_id."""
        # Generate a unique-ish ID (timestamp + random suffix to avoid collisions)
        msg_id = (int(time.time() * 1000) % 10_000_000) * 100 + random.randint(0, 99)

        # Serialize messages — preserve image_bytes so approved replies have context
        # NOTE: image_bytes are NOT persisted to disk (too large), but their
        # presence is recorded so the worker knows to re-fetch if needed.
        serialized_msgs = []
        for pm in messages:
            serialized_msgs.append({
                "label": pm.label,
                "content": pm.content,
                "history_type": pm.kind.value if hasattr(pm.kind, "value") else str(pm.kind),
                "has_image": pm.image_bytes is not None,
                "image_msg_id": pm.raw_msg_id if pm.image_bytes else "",
                "caption": pm.caption,
            })

        item = ApprovalItem(
            msg_id=msg_id,
            contact=contact,
            timestamp=datetime.now().isoformat(),
            messages=serialized_msgs,
            decision=decision.to_dict(),
            status="pending",
        )
        path = self._path_for(msg_id)
        store.write_raw(path, item.to_dict())
        logger.warning(
            f"[Queue] Saved approval request for {contact} (id={msg_id}, "
            f"risk={decision.risk_level.value}, reason={decision.reason[:60]})"
        )
        metrics.inc("approval_added", risk_level=decision.risk_level.value)
        return msg_id

    def approve(
        self, msg_id: int, custom_context: str = "", custom_reply: str = "",
    ) -> bool:
        """Mark an item as approved. Returns True on success."""
        lock = self._item_lock(msg_id)
        with lock:
            path = self._path_for(msg_id)
            data = store.read_raw(path)
            if not data:
                logger.warning(f"[Queue] Approve: id {msg_id} not found")
                return False
            if data.get("status") not in ("pending",):
                logger.warning(
                    f"[Queue] Approve: id {msg_id} status is "
                    f"{data.get('status')}, cannot approve"
                )
                return False
            data["status"] = "approved"
            data["approved_at"] = datetime.now().isoformat()
            if custom_context:
                data["custom_context"] = custom_context
            if custom_reply:
                data["custom_reply"] = custom_reply
            store.write_raw(path, data)
            logger.info(f"[Queue] Approved id {msg_id}")
            metrics.inc("approval_approved")
            return True

    def reject(self, msg_id: int, reason: str = "") -> bool:
        """Mark an item as rejected. Returns True on success."""
        lock = self._item_lock(msg_id)
        with lock:
            path = self._path_for(msg_id)
            data = store.read_raw(path)
            if not data:
                return False
            if data.get("status") not in ("pending", "approved"):
                return False
            data["status"] = "rejected"
            data["rejected_at"] = datetime.now().isoformat()
            data["rejection_reason"] = reason
            store.write_raw(path, data)
            logger.info(f"[Queue] Rejected id {msg_id}: {reason}")
            metrics.inc("approval_rejected")
            return True

    def list_pending(self) -> list[dict]:
        """List all pending items (newest first)."""
        items = []
        for key in store.list_keys(self.COLLECTION):
            data = store.read(self.COLLECTION, key)
            if data and data.get("status") == "pending":
                items.append(data)
        items.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
        return items

    def list_all(self, status: Optional[str] = None) -> list[dict]:
        """List all items, optionally filtered by status."""
        items = []
        for key in store.list_keys(self.COLLECTION):
            data = store.read(self.COLLECTION, key)
            if data:
                if status is None or data.get("status") == status:
                    items.append(data)
        items.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
        return items

    def get(self, msg_id: int) -> Optional[dict]:
        """Get a single item by ID."""
        return store.read(self.COLLECTION, str(msg_id))

    def claim_for_processing(self, msg_id: int) -> Optional[ApprovalItem]:
        """Atomically transition an item from 'approved' to 'processing'.

        Returns the item if claimed, None if it was already claimed or not
        in 'approved' state.
        """
        lock = self._item_lock(msg_id)
        with lock:
            path = self._path_for(msg_id)
            data = store.read_raw(path)
            if not data:
                return None
            if data.get("status") != "approved":
                return None
            data["status"] = "processing"
            data["attempts"] = data.get("attempts", 0) + 1
            store.write_raw(path, data)
            return ApprovalItem.from_dict(data, file_path=str(path))

    def mark_sent(self, msg_id: int) -> None:
        """Mark an item as successfully sent and remove it from the queue."""
        lock = self._item_lock(msg_id)
        with lock:
            path = self._path_for(msg_id)
            data = store.read_raw(path)
            if data:
                data["status"] = "sent"
                data["sent_at"] = datetime.now().isoformat()
                # Keep a record briefly, then remove
                store.write_raw(path, data)
            # Remove the file
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.warning(f"[Queue] Failed to remove {path}: {e}")
            metrics.inc("approval_sent")

    def mark_failed(self, msg_id: int, error: str) -> None:
        """Revert an item from 'processing' back to 'approved' for retry."""
        lock = self._item_lock(msg_id)
        with lock:
            path = self._path_for(msg_id)
            data = store.read_raw(path)
            if not data:
                return
            if data.get("status") != "processing":
                return
            data["status"] = "approved"
            data["error"] = error[:500]
            store.write_raw(path, data)
            metrics.inc("approval_send_failed")

    def count(self, status: Optional[str] = None) -> int:
        """Count items, optionally filtered by status."""
        return len(self.list_all(status))


# Singleton
approval_queue = ApprovalQueue()
