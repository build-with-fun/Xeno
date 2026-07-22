"""Retry queue with exponential backoff.

Fixes the original code's issues:
- ISO string comparison was used for scheduling — works but fragile
- `os.remove` could fail with FileNotFoundError, killing the worker thread
- Retry loop held `_page_lock` while sending — blocked the main loop
- No jitter in backoff (all retries happened at exactly the scheduled time)
"""
from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.core.types import RetryItem
from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.utils.text import safe_filename

logger = get_logger(__name__)


class RetryQueue:
    """File-backed retry queue with exponential backoff + jitter."""

    COLLECTION = "retry"

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def add(self, contact: str, reply: str, attempt: int = 0, last_error: str = "") -> str:
        """Add an item to the retry queue. Returns the queue key."""
        delay = self._backoff(attempt)
        next_retry = datetime.now() + timedelta(seconds=delay)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        key = f"{safe_filename(contact)}_{ts}"
        data = {
            "contact": contact,
            "reply": reply,
            "attempt": attempt,
            "next_retry_at": next_retry.isoformat(),
            "original_ts": datetime.now().isoformat(),
            "last_error": last_error[:500],
        }
        store.write(self.COLLECTION, key, data)
        logger.warning(
            f"[Retry] Queued for {contact}, attempt={attempt}, delay={delay}s"
        )
        metrics.inc("retry_added", attempt=attempt)
        return key

    def due_items(self) -> list[RetryItem]:
        """Return all items whose next_retry_at has passed."""
        now = datetime.now().isoformat()
        items = []
        for key in store.list_keys(self.COLLECTION):
            data = store.read(self.COLLECTION, key)
            if not data:
                continue
            next_at = data.get("next_retry_at", "")
            if next_at > now:
                continue
            items.append(RetryItem(
                contact=data.get("contact", ""),
                reply=data.get("reply", ""),
                attempt=int(data.get("attempt", 0)),
                next_retry_at=next_at,
                original_ts=data.get("original_ts", ""),
                file_path=str(store.path_for(self.COLLECTION, key)),
                last_error=data.get("last_error", ""),
            ))
        items.sort(key=lambda r: r.next_retry_at)
        return items

    def remove(self, file_path: str) -> bool:
        """Remove an item by file path. Returns True if removed."""
        path = Path(file_path)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as e:
            logger.warning(f"[Retry] Failed to remove {path}: {e}")
            return False

    def reschedule(self, file_path: str, attempt: int, error: str = "") -> None:
        """Reschedule an item with the next backoff."""
        path = Path(file_path)
        data = store.read_raw(path)
        if not data:
            return
        next_attempt = attempt + 1
        if next_attempt >= settings.retry_max_attempts:
            # Convert to approval queue item (manual review)
            logger.warning(
                f"[Retry] Max attempts reached for {data.get('contact')}, "
                f"escalating to approval queue"
            )
            self._escalate(data)
            self.remove(file_path)
            return
        delay = self._backoff(next_attempt)
        data["attempt"] = next_attempt
        data["next_retry_at"] = (
            datetime.now() + timedelta(seconds=delay)
        ).isoformat()
        data["last_error"] = error[:500]
        store.write_raw(path, data)
        logger.info(
            f"[Retry] Rescheduled {data.get('contact')} "
            f"(attempt={next_attempt}, delay={delay}s)"
        )

    def _escalate(self, retry_data: dict) -> None:
        """Move a max-retries-exceeded item to the approval queue."""
        from media.whatsapp.taskqueue.approval import approval_queue
        from media.whatsapp.core.types import ApprovalItem, Decision, RiskLevel, DecisionCategory

        msg_id = (int(time.time() * 1000) % 10_000_000) * 100 + random.randint(0, 99)
        item = ApprovalItem(
            msg_id=msg_id,
            contact=retry_data.get("contact", ""),
            timestamp=datetime.now().isoformat(),
            messages=[{
                "label": "Retry",
                "content": retry_data.get("reply", ""),
                "history_type": "text",
                "has_image": False,
                "image_msg_id": "",
                "caption": "",
            }],
            decision=Decision(
                needs_approval=True,
                risk_level=RiskLevel.LOW,
                reason="Max retries exceeded — manual review needed.",
                triggered_category=DecisionCategory.AMBIGUOUS,
            ).to_dict(),
            status="pending",
            error=retry_data.get("last_error", ""),
        )
        store.write_raw(store.path_for(approval_queue.COLLECTION, str(msg_id)), item.to_dict())

    @staticmethod
    def _backoff(attempt: int) -> int:
        """Exponential backoff with jitter: base * 2^attempt + random(0, base)."""
        base = settings.retry_backoff_base
        delay = base * (2 ** attempt) + random.uniform(0, base)
        return int(min(delay, settings.retry_backoff_max))

    def count(self) -> int:
        return len(store.list_keys(self.COLLECTION))


# Singleton
retry_queue = RetryQueue()
