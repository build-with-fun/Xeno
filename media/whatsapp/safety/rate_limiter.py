"""Per-contact rate limiter (anti-spam & anti-detection).

The original code had NO per-contact rate limiting — a single contact
sending 100 messages would trigger 100 AI calls and 100 replies within
minutes, which is a fast track to a WhatsApp ban.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter per contact.

    Tracks reply timestamps per contact. If a contact has received more
    than `rate_limit_per_hour` replies in the last hour, all further
    replies are held for `rate_limit_cooldown` seconds.
    """

    def __init__(
        self,
        max_per_hour: int = settings.rate_limit_per_hour,
        cooldown_secs: int = settings.rate_limit_cooldown,
    ):
        self._max = max_per_hour
        self._cooldown = cooldown_secs
        self._lock = threading.RLock()
        self._timestamps: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}

    def can_reply(self, contact: str) -> bool:
        """Return True if we can reply to this contact right now."""
        now = time.time()
        with self._lock:
            # Check explicit block
            blocked_until = self._blocked_until.get(contact, 0)
            if now < blocked_until:
                metrics.inc("rate_limit_blocked", contact=contact)
                return False
            # Prune old timestamps (older than 1 hour)
            dq = self._timestamps.get(contact)
            if dq is None:
                return True
            cutoff = now - 3600
            while dq and dq[0] < cutoff:
                dq.popleft()
            return len(dq) < self._max

    def record_reply(self, contact: str) -> None:
        """Record that we sent a reply to this contact."""
        now = time.time()
        with self._lock:
            dq = self._timestamps.setdefault(contact, deque())
            dq.append(now)
            # If we just hit the limit, block for cooldown
            if len(dq) >= self._max:
                self._blocked_until[contact] = now + self._cooldown
                logger.warning(
                    f"[RateLimit] {contact} hit hourly limit ({self._max}); "
                    f"blocking for {self._cooldown}s"
                )
                metrics.inc("rate_limit_triggered", contact=contact)

    def status(self, contact: str) -> dict:
        """Return current rate-limit status for a contact."""
        now = time.time()
        with self._lock:
            dq = self._timestamps.get(contact, deque())
            cutoff = now - 3600
            recent = [t for t in dq if t >= cutoff]
            blocked_until = self._blocked_until.get(contact, 0)
            return {
                "contact": contact,
                "replies_last_hour": len(recent),
                "max_per_hour": self._max,
                "blocked": now < blocked_until,
                "blocked_until": blocked_until if blocked_until > now else 0,
                "cooldown_secs": self._cooldown,
            }


# Singleton
rate_limiter = RateLimiter()
