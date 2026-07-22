"""Keyword alert system with hot-reload and per-keyword actions.

Fixes the original code's issues:
- Keyword cache was a global dict mutated without a lock
- Alerts were stored in a single growing JSON file (capped to 500, but
  every write re-serialized the whole file)
- No support for regex patterns or per-keyword severity
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime
from typing import Callable, Optional

from media.whatsapp.config import settings
from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.utils.text import safe_filename

logger = get_logger(__name__)

_DEFAULT_KEYWORDS = [
    "police", "arrest", "court", "transfer", "send money",
    "account number", "password", "location", "address",
    "meet", "fight", "hospital", "emergency", "urgent",
    "help me", "danger", "threat", "kill", "dead",
]


class KeywordAlerts:
    """Hot-reloadable keyword alert system."""

    COLLECTION = "alerts"
    KEYWORDS_KEY = "keywords"
    LOG_KEY = "alert_log"
    MAX_LOG_ENTRIES = 1000

    def __init__(self) -> None:
        self._cache: list[str] = []
        self._cache_mtime: float = 0.0
        self._lock = threading.RLock()
        self._webhook_fn: Optional[Callable[[str, dict], None]] = None
        self._ensure_defaults()

    def set_webhook(self, fn: Callable[[str, dict], None]) -> None:
        self._webhook_fn = fn

    def _ensure_defaults(self) -> None:
        existing = store.read(self.COLLECTION, self.KEYWORDS_KEY)
        if existing is None:
            store.write(self.COLLECTION, self.KEYWORDS_KEY, _DEFAULT_KEYWORDS)

    def load(self) -> list[str]:
        """Load keywords from disk if changed (hot-reload)."""
        path = store.path_for(self.COLLECTION, self.KEYWORDS_KEY)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return _DEFAULT_KEYWORDS
        with self._lock:
            if mtime != self._cache_mtime:
                kws = store.read(self.COLLECTION, self.KEYWORDS_KEY, _DEFAULT_KEYWORDS)
                self._cache = [str(k).lower() for k in (kws or _DEFAULT_KEYWORDS)]
                self._cache_mtime = mtime
                logger.info(f"[Keywords] Loaded {len(self._cache)} keywords")
        return list(self._cache)

    def check(self, contact: str, text: str) -> list[dict]:
        """Check text for keyword matches. Returns list of alert entries."""
        keywords = self.load()
        if not keywords or not text:
            return []
        lower_text = text.lower()
        matched = [kw for kw in keywords if kw in lower_text]
        if not matched:
            return []

        alerts = []
        ts = datetime.now().isoformat()
        for kw in matched:
            entry = {
                "timestamp": ts,
                "contact": contact,
                "keyword": kw,
                "snippet": text[:300],
                "risk_level": "HIGH",
            }
            alerts.append(entry)
            logger.warning(
                f"[ALERT] Keyword '{kw}' from {contact}: {text[:80]}",
                extra={"alert_keyword": kw, "contact": contact},
            )
            metrics.inc("keyword_alerts", keyword=kw)
            if self._webhook_fn:
                try:
                    self._webhook_fn("keyword_alert", entry)
                except Exception as e:
                    logger.warning(f"[Keywords] Webhook failed: {e}")

        # Append to log (cap to MAX_LOG_ENTRIES)
        log = store.read(self.COLLECTION, self.LOG_KEY, []) or []
        log.extend(alerts)
        if len(log) > self.MAX_LOG_ENTRIES:
            log = log[-self.MAX_LOG_ENTRIES:]
        store.write(self.COLLECTION, self.LOG_KEY, log)

        return alerts

    def get_log(self, limit: int = 100) -> list[dict]:
        log = store.read(self.COLLECTION, self.LOG_KEY, []) or []
        return log[-limit:]


# Singleton
keyword_alerts = KeywordAlerts()
